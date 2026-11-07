#!/usr/bin/env python3
"""
Agent JuriAgent: comprendre -> rechercher -> rediger (format fixe) -> verifier.

Principes: explique sans juger, chaque affirmation sourcee [Article X],
abstention si le corpus ne suffit pas, orientation vers un humain.
Modeles Meta: redaction muse-spark-1.3, verification muse-spark-1.3 (appel separe).

Usage:
  python src/agent/agent.py --question "mon pere est decede, comment partager son terrain ?"
  python src/agent/agent.py --question "..." --type heritage --commune Abomey-Calavi
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from search.search import Searcher          # noqa: E402
from verifier.verifier import deterministic_filter, model_check, deadline_warnings  # noqa: E402
from agent.contacts import contacts_for   # noqa: E402

ORIENTATION = (
    "Cet assistant reste disponible pour expliquer les textes, les delais et les demarches. "
    "Pour un avis sur votre situation precise, un avocat, l'Agence Nationale du Domaine et du Foncier (ANDF), "
    "votre mairie ou le tribunal competent peuvent vous accompagner."
)

AVIS_STANDARD = (
    "Je ne peux pas donner d'avis sur l'issue de votre situation (qui a raison, vos chances, la strategie a suivre). "
    "En revanche, je peux vous expliquer ce que disent les textes: voici les articles qui s'appliquent."
)


MODEL = "muse-spark-1.3"


def _env(name: str) -> str:
    import os
    if os.environ.get(name):
        return os.environ[name]
    if Path(".env").exists():
        for line in Path(".env").read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    return ""


def load_client():
    """Fournisseur d'inference Meta, au choix (JURI_MODEL_PROVIDER):
    - meta    : Muse Spark via api.meta.ai (defaut)
    - baseten : Muse Spark Open (open-weights Meta) via inference.baseten.co
    """
    global MODEL
    from openai import OpenAI
    provider = (_env("JURI_MODEL_PROVIDER") or "meta").lower()
    if provider == "baseten":
        key = _env("BASETEN_API_KEY")
        if not key:
            print("BASETEN_API_KEY manquante dans .env", file=sys.stderr)
            sys.exit(2)
        MODEL = _env("BASETEN_MODEL") or "meta-models/muse-spark-open-1026"
        print(f"fournisseur: baseten ({MODEL})", file=sys.stderr)
        return OpenAI(api_key=key, base_url="https://inference.baseten.co/v1")
    key = _env("META_API_KEY")
    if not key:
        print("META_API_KEY manquante dans .env", file=sys.stderr)
        sys.exit(2)
    MODEL = _env("META_MODEL") or "muse-spark-1.3"
    return OpenAI(api_key=key, base_url="https://api.meta.ai/v1")


def expand_queries(client, question: str, situation: dict) -> list[str]:
    prompt = (
        "Transforme cette situation citoyenne en 3 requetes de recherche juridique courtes "
        "(mots-cles du code foncier beninois: titre foncier, confirmation de droits, expropriation, "
        "succession, plan foncier rural, prescription...). Reponds en JSON: {\"requetes\": [..]}.\n"
        f"Situation: {json.dumps(situation, ensure_ascii=False)}\nQuestion: {question}"
    )
    try:
        r = client.chat.completions.create(model=MODEL,
                                           messages=[{"role": "user", "content": prompt}], max_tokens=1500, temperature=0.2)
        m = re.search(r"\{.*\}", r.choices[0].message.content or "", re.DOTALL)
        qs = json.loads(m.group(0)).get("requetes", []) if m else []
        return [q for q in qs if q][:3] or [question]
    except Exception:
        return [question]


def build_context(historique: list | None, question: str) -> str:
    """Contexte conversationnel: les tours utilisateur precedents + la question.
    L'historique vit cote client (anonymat: rien stocke serveur)."""
    parts = []
    for h in historique or []:
        texte = h.get("texte", "") if isinstance(h, dict) else str(h)
        role = h.get("role", "utilisateur") if isinstance(h, dict) else "utilisateur"
        if texte.strip() and role in ("utilisateur", "user"):
            parts.append(texte.strip())
    if question.strip() and (not parts or parts[-1] != question.strip()):
        parts.append(question.strip())
    return " ".join(parts)


_TYPE_KW = ("heritage", "succession", "titre", "expropriation", "expulsion",
            "partage", "occupation", "decede", "terrain occupe")
_DOC_KW = ("titre foncier", "recepisse", "acte", "certificat", "jugement",
           "plan foncier", "document", "papier")
_ADV_KW = ("voisin", "etat", "mairie", "famille", "frere", "soeur", "oncle",
           "administration", "particulier", "quelqu'un", "un homme", "une femme")
_LEGAL_Q_KW = ("comment", "quel", "quels", "quelles", "delai", "procedure",
               "obtenir", "faire pour", "demarche", "qui peut", "combien")


def missing_slots(contexte: str, situation: dict) -> list[str]:
    """Informations essentielles manquantes (fiche de route section 5, etape 1)."""
    c = contexte.lower()
    out = []
    if not situation.get("type") and not any(k in c for k in _TYPE_KW):
        out.append("De quoi s'agit-il : heritage, titre foncier, expropriation, expulsion ou partage ?")
    if not re.search(r"(19|20)\d{2}|depuis \d|/(\d{4})", c):
        out.append("Depuis quand, ou en quelle annee, cela a-t-il commence ?")
    if not situation.get("documents") and not any(k in c for k in _DOC_KW):
        out.append("Quels documents avez-vous deja (titre, acte, recepisse, jugement...) ?")
    if not situation.get("adversaire") and not any(k in c for k in _ADV_KW):
        out.append("Qui est l'autre partie : un particulier, la famille ou l'administration ?")
    return out


def clarification_needed(contexte: str, situation: dict, historique: list | None) -> list[str]:
    """Clarifie au lieu de chercher quand le probleme est expose de facon trop
    vague au premier tour. Jamais si l'utilisateur a deja repondu (historique),
    ni si la question juridique est claire."""
    deja = [h for h in (historique or []) if isinstance(h, dict) and h.get("role") in ("utilisateur", "user")]
    if deja:
        return []
    c = contexte.lower()
    # Type deja connu (menu ou mots-cles) ou demande de verdict/penal: ces cas
    # ont deja un traitement en aval, ne pas les detourner en clarification.
    if situation.get("type") or any(k in c for k in _TYPE_KW):
        return []
    if any(k in c for k in ("prison", "condamne", "gagner", "coupable", "peine")):
        return []
    slots = missing_slots(contexte, situation)
    mots = len(re.findall(r"\w+", contexte))
    claire = any(k in contexte.lower() for k in _LEGAL_Q_KW)
    return slots[:3] if (mots < 18 and len(slots) >= 3 and not claire) else []


def _soft_abstention(raison: str, contexte: str, situation: dict, **extra) -> dict:
    """Abstention douce: on dit ce qui manque et comment continuer, au lieu
    d'une porte fermee. abstention reste true (securite juridique)."""
    relance = missing_slots(contexte, situation)[:3]
    return {"abstention": True, "raison": raison, "orientation": ORIENTATION,
            "relance": relance,
            "message": ("Je n'ai pas encore assez d'elements sources pour repondre a ce point. "
                        "Vous pouvez me preciser ce qui suit, ou me poser une question plus precise "
                        "sur un texte, un delai ou une demarche."),
            **extra}


def retrieve(searcher: Searcher, queries: list[str], top_k: int = 8, client=None, question: str = "") -> list[dict]:
    seen, out = set(), []
    for q in queries:
        for r in searcher.search(q, top_k=6):
            if r["id"] not in seen:
                seen.add(r["id"])
                full = next(x for x in searcher.rows if x["id"] == r["id"])
                out.append(full)
    out = out[:18]
    if client is not None and len(out) > top_k:
        out = rerank(client, question, out, top_k)
    return out[:top_k]


def rerank(client, question: str, passages: list[dict], top_k: int) -> list[dict]:
    """Re-classement par Muse Spark (modele Meta): aucun modele tiers a l'execution."""
    listing = "\n".join(f"{i}. [Article {p['article']}] {p['texte'][:250]}" for i, p in enumerate(passages))
    prompt = (
        "Classe ces passages du code foncier beninois du plus pertinent au moins pertinent "
        f"pour la question: {question}\nReponds en JSON: {{\"ordre\": [indices]}}.\n\n{listing}"
    )
    try:
        r = client.chat.completions.create(model=MODEL,
                                           messages=[{"role": "user", "content": prompt}],
                                           max_tokens=1500, temperature=0)
        m = re.search(r"\{.*\}", r.choices[0].message.content or "", re.DOTALL)
        order = json.loads(m.group(0)).get("ordre", []) if m else []
        picked = [passages[i] for i in order if isinstance(i, int) and 0 <= i < len(passages)]
        rest = [p for p in passages if p not in picked]
        return (picked + rest)[:top_k]
    except Exception:
        return passages[:top_k]


def draft(client, question: str, situation: dict, passages: list[dict], force_info: bool = False) -> dict:
    corpus = "\n\n".join(
        f"[Article {p['article']}] ({p.get('statut')}; {p.get('lien_source') or ''})\n{p['texte'][:1800]}"
        for p in passages)
    regle_abstention = (
        "Les passages ci-dessus concernent le sujet: ne t'abstiens pas. Explique ce que disent les textes "
        "et refuse seulement l'avis (avis_refuse: true)."
        if force_info else
        "Mets \"abstention\": true UNIQUEMENT si aucun passage ne concerne le sujet de la question (hors corpus foncier)."
    )
    prompt = (
        "Tu es un assistant d'information sur le droit foncier du Benin. Tu expliques, tu ne juges pas: "
        "jamais de verdict, jamais de pronostic sur l'issue, jamais de strategie.\n"
        "Regles:\n"
        f"- {regle_abstention}\n"
        "- Si la question demande un avis (qui a raison, vais-je gagner, mes chances, quelle strategie): "
        "ne t'abstiens pas pour autant. Mets \"avis_refuse\": true et ecris dans \"avis\" une phrase courte "
        "disant que tu ne donnes pas d'avis sur l'issue mais que tu peux expliquer ce que disent les textes. "
        "Reponds quand meme a la partie information (loi, demarches, pieces, delais).\n"
        "- Chaque affirmation de la section 'loi' doit citer [Article X] present dans les passages.\n"
        "Reponds UNIQUEMENT en JSON:\n"
        "{\"abstention\": false, \"avis_refuse\": false, \"avis\": \"\", \"loi\": [{\"texte\": \"... [Article X]\"}], "
        "\"simple\": \"...\", \"demarches\": [\"...\"], \"pieces\": [\"...\"], \"delais\": [\"...\"], \"adresses\": [\"...\"]}\n\n"
        f"Situation: {json.dumps(situation, ensure_ascii=False)}\nQuestion: {question}\n\nPASSAGES:\n{corpus}"
    )
    r = client.chat.completions.create(model=MODEL,
                                       messages=[{"role": "user", "content": prompt}], max_tokens=6000, temperature=0.2)
    m = re.search(r"\{.*\}", r.choices[0].message.content or "", re.DOTALL)
    return json.loads(m.group(0)) if m else {"abstention": True}


def run(question: str, situation: dict, searcher: Searcher | None = None,
         historique: list | None = None) -> dict:
    contexte = build_context(historique, question)
    questions_clarif = clarification_needed(contexte, situation, historique)
    if questions_clarif:  # etape 1 (comprendre) avant de chercher
        return {"abstention": False, "clarification": True, "questions": questions_clarif,
                "message": "Pour chercher le bon texte, j'ai besoin de quelques precisions :",
                "orientation": ORIENTATION}
    client = load_client()
    if searcher is None:
        searcher = Searcher(use_semantic=True)
    queries = expand_queries(client, contexte, situation)
    passages = retrieve(searcher, queries, client=client, question=contexte)
    if not passages:
        return _soft_abstention("aucun passage pertinent", contexte, situation)
    ans = draft(client, contexte, situation, passages)
    if ans.get("abstention"):
        ans = draft(client, contexte, situation, passages, force_info=True)  # relance: expliquer au lieu d'esquiver
    if ans.get("abstention"):
        return _soft_abstention("hors corpus", contexte, situation,
                                contacts=contacts_for(situation),
                                sources=[p["article"] for p in passages])
    claims = deterministic_filter(ans.get("loi", []), passages)
    claims = model_check(client, MODEL, claims, passages)
    if not claims:
        return _soft_abstention("affirmations non appuyees par le corpus", contexte, situation,
                                contacts=contacts_for(situation),
                                sources=[{"article": p["article"], "statut": p.get("statut"),
                                          "lien": p.get("lien_source")} for p in passages])
    ans["loi"] = claims
    ans["avis_refuse"] = bool(ans.get("avis_refuse"))
    if ans["avis_refuse"] and not (ans.get("avis") or "").strip():
        ans["avis"] = AVIS_STANDARD
    ans["delais_signales"] = deadline_warnings(passages)
    ans["contacts"] = contacts_for(situation)
    ans["sources"] = [{"article": p["article"], "statut": p.get("statut"), "lien": p.get("lien_source")} for p in passages]
    ans["requetes"] = queries
    ans["limite"] = ("Cet assistant explique les textes; il ne peut pas dire qui a raison ni quelle strategie adopter. "
                      "Ne partagez pas d'informations personnelles identifiantes (noms complets, numeros d'identite, de telephone ou de titres). "
                      + ORIENTATION)
    return ans


def main():
    ap = argparse.ArgumentParser(description="JuriAgent")
    ap.add_argument("--question", required=True)
    ap.add_argument("--type", default="", help="heritage|titre|expropriation|expulsion|partage")
    ap.add_argument("--commune", default="")
    ap.add_argument("--documents", default="")
    ap.add_argument("--adversaire", default="", help="particulier|Etat")
    args = ap.parse_args()
    situation = {k: v for k, v in vars(args).items() if k != "question" and v}
    print(json.dumps(run(args.question, situation), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
