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
    "Pour une analyse de votre situation precise, adressez-vous a un avocat, "
    "a l'Agence Nationale du Domaine et du Foncier (ANDF), a votre mairie ou au tribunal competent."
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


def draft(client, question: str, situation: dict, passages: list[dict]) -> dict:
    corpus = "\n\n".join(
        f"[Article {p['article']}] ({p.get('statut')}; {p.get('lien_source') or ''})\n{p['texte'][:1800]}"
        for p in passages)
    prompt = (
        "Tu es un assistant d'information sur le droit foncier du Benin. Tu expliques, tu ne juges pas: "
        "jamais de verdict, jamais de strategie. Mets \"abstention\": true UNIQUEMENT si aucun passage ne concerne le sujet de la question. Chaque affirmation de la section 'loi' doit citer "
        "[Article X] present dans les passages. Si les passages ne permettent pas de repondre, mets "
        "\"abstention\": true. Reponds UNIQUEMENT en JSON:\n"
        "{\"abstention\": false, \"loi\": [{\"texte\": \"... [Article X]\"}], \"simple\": \"...\", "
        "\"demarches\": [\"...\"], \"pieces\": [\"...\"], \"delais\": [\"...\"], \"adresses\": [\"...\"]}\n\n"
        f"Situation: {json.dumps(situation, ensure_ascii=False)}\nQuestion: {question}\n\nPASSAGES:\n{corpus}"
    )
    r = client.chat.completions.create(model=MODEL,
                                       messages=[{"role": "user", "content": prompt}], max_tokens=6000, temperature=0.2)
    m = re.search(r"\{.*\}", r.choices[0].message.content or "", re.DOTALL)
    return json.loads(m.group(0)) if m else {"abstention": True}


def run(question: str, situation: dict, searcher: Searcher | None = None) -> dict:
    client = load_client()
    if searcher is None:
        searcher = Searcher(use_semantic=True)
    queries = expand_queries(client, question, situation)
    passages = retrieve(searcher, queries, client=client, question=question)
    if not passages:
        return {"abstention": True, "raison": "aucun passage pertinent", "orientation": ORIENTATION}
    ans = draft(client, question, situation, passages)
    if ans.get("abstention"):
        ans = draft(client, question, situation, passages)  # relance unique: abstentions intermittentes observees
    if ans.get("abstention"):
        return {"abstention": True, "orientation": ORIENTATION, "contacts": contacts_for(situation),
                "sources": [p["article"] for p in passages]}
    claims = deterministic_filter(ans.get("loi", []), passages)
    claims = model_check(client, MODEL, claims, passages)
    if not claims:
        return {"abstention": True, "raison": "affirmations non appuyees par le corpus", "orientation": ORIENTATION}
    ans["loi"] = claims
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
