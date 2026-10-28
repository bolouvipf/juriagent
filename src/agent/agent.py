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

ORIENTATION = (
    "Pour une analyse de votre situation precise, adressez-vous a un avocat, "
    "a l'Agence Nationale du Domaine et du Foncier (ANDF), a votre mairie ou au tribunal competent."
)


def load_client():
    from openai import OpenAI
    key = ""
    for line in Path(".env").read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        if line.startswith("META_API_KEY="):
            key = line.split("=", 1)[1].strip()
    if not key:
        print("META_API_KEY manquante dans .env", file=sys.stderr)
        sys.exit(2)
    return OpenAI(api_key=key, base_url="https://api.meta.ai/v1")


def expand_queries(client, question: str, situation: dict) -> list[str]:
    prompt = (
        "Transforme cette situation citoyenne en 3 requetes de recherche juridique courtes "
        "(mots-cles du code foncier beninois: titre foncier, confirmation de droits, expropriation, "
        "succession, plan foncier rural, prescription...). Reponds en JSON: {\"requetes\": [..]}.\n"
        f"Situation: {json.dumps(situation, ensure_ascii=False)}\nQuestion: {question}"
    )
    try:
        r = client.chat.completions.create(model="muse-spark-1.3",
                                           messages=[{"role": "user", "content": prompt}], max_tokens=1500, temperature=0.2)
        m = re.search(r"\{.*\}", r.choices[0].message.content or "", re.DOTALL)
        qs = json.loads(m.group(0)).get("requetes", []) if m else []
        return [q for q in qs if q][:3] or [question]
    except Exception:
        return [question]


def retrieve(searcher: Searcher, queries: list[str], top_k: int = 8) -> list[dict]:
    seen, out = set(), []
    for q in queries:
        for r in searcher.search(q, top_k=4):
            if r["id"] not in seen:
                seen.add(r["id"])
                full = next(x for x in searcher.rows if x["id"] == r["id"])
                out.append(full)
    return out[:top_k]


def draft(client, question: str, situation: dict, passages: list[dict]) -> dict:
    corpus = "\n\n".join(
        f"[Article {p['article']}] ({p.get('statut')}; {p.get('lien_source') or ''})\n{p['texte'][:1800]}"
        for p in passages)
    prompt = (
        "Tu es un assistant d'information sur le droit foncier du Benin. Tu expliques, tu ne juges pas: "
        "jamais de verdict, jamais de strategie. Chaque affirmation de la section 'loi' doit citer "
        "[Article X] present dans les passages. Si les passages ne permettent pas de repondre, mets "
        "\"abstention\": true. Reponds UNIQUEMENT en JSON:\n"
        "{\"abstention\": false, \"loi\": [{\"texte\": \"... [Article X]\"}], \"simple\": \"...\", "
        "\"demarches\": [\"...\"], \"pieces\": [\"...\"], \"delais\": [\"...\"], \"adresses\": [\"...\"]}\n\n"
        f"Situation: {json.dumps(situation, ensure_ascii=False)}\nQuestion: {question}\n\nPASSAGES:\n{corpus}"
    )
    r = client.chat.completions.create(model="muse-spark-1.3",
                                       messages=[{"role": "user", "content": prompt}], max_tokens=6000, temperature=0.2)
    m = re.search(r"\{.*\}", r.choices[0].message.content or "", re.DOTALL)
    return json.loads(m.group(0)) if m else {"abstention": True}


def run(question: str, situation: dict, searcher: Searcher | None = None) -> dict:
    client = load_client()
    if searcher is None:
        searcher = Searcher(use_semantic=True)
    queries = expand_queries(client, question, situation)
    passages = retrieve(searcher, queries)
    if not passages:
        return {"abstention": True, "raison": "aucun passage pertinent", "orientation": ORIENTATION}
    ans = draft(client, question, situation, passages)
    if ans.get("abstention"):
        return {"abstention": True, "orientation": ORIENTATION,
                "sources": [p["article"] for p in passages]}
    claims = deterministic_filter(ans.get("loi", []), passages)
    claims = model_check(client, "muse-spark-1.3", claims, passages)
    if not claims:
        return {"abstention": True, "raison": "affirmations non appuyees par le corpus", "orientation": ORIENTATION}
    ans["loi"] = claims
    ans["delais_signales"] = deadline_warnings(passages)
    ans["sources"] = [{"article": p["article"], "statut": p.get("statut"), "lien": p.get("lien_source")} for p in passages]
    ans["requetes"] = queries
    ans["limite"] = "Cet assistant explique les textes; il ne peut pas dire qui a raison ni quelle strategie adopter. " + ORIENTATION
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
