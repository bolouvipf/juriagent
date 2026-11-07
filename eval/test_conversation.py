#!/usr/bin/env python3
"""Conversation multi-tours: clarification, contexte accumule, abstention
douce, suivi procedure. Deterministe, sans LLM ni reseau (run() renvoie la
clarification avant tout appel modele).
Usage: python eval/test_conversation.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from agent.agent import build_context, clarification_needed, missing_slots, run, _soft_abstention  # noqa: E402
from search.procedure import ProcedureCorpus  # noqa: E402
from agent.procedure_agent import answer  # noqa: E402

fails = []


def check(name, cond, detail=""):
    print(("OK  " if cond else "FAIL") + f" {name} {detail}")
    if not cond:
        fails.append(name)


# 1. Probleme vague, premier tour -> clarification (pas de recherche, pas de LLM)
r = run("j'ai un probleme de terrain", {})
check("C1 clarification vague", r.get("clarification") and len(r.get("questions", [])) >= 2, str(r.get("questions")))

# 2. Question juridique claire -> pas de clarification
q = "Comment obtenir un titre foncier pour mon terrain ?"
check("C2 question claire", clarification_needed(build_context(None, q), {}, None) == [])

# 3. Les questions d'eval existantes ne doivent pas etre detournees en clarification
qs = json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
items = qs if isinstance(qs, list) else qs.get("questions", [])
detournees = []
for x in items:  # meme situation que eval/run_eval.py
    sit = {k: x[k] for k in ("type", "commune", "documents", "adversaire") if x.get(k)}
    if clarification_needed(build_context(None, x.get("question", "")), sit, None):
        detournees.append(x.get("id", "?"))
check("C3 eval non detournee", not detournees, str(detournees))

# 4. Contexte accumule: le suivi seul ne veut rien dire, avec l'historique oui
hist = [{"role": "utilisateur", "texte": "Mon pere est decede en 2019, nous avons un recepisse"}]
ctx = build_context(hist, "et pour le partage ?")
check("C4 contexte accumule", "2019" in ctx and "partage" in ctx and "recepisse" in ctx, ctx[:80])

# 5. Apres un premier tour, plus de clarification forcee (l'utilisateur repond)
check("C5 pas de re-clarification", clarification_needed(ctx, {}, hist) == [])

# 6. Abstention douce: raison conservee + relance concrete
r = _soft_abstention("hors corpus", "probleme vague", {})
check("C6 abstention douce", r["abstention"] and r["raison"] == "hors corpus" and len(r["relance"]) >= 1)

# 7. Procedure multi-tours: le suivi "et pour le juge de l'execution ?" retrouve 589 nouveau
c = ProcedureCorpus()
r = answer(c, "et pour le juge de l'execution ?",
           historique=[{"role": "utilisateur", "texte": "Quel est le delai d'appel ?"}])
ids = [x["id"] for x in r.get("loi", [])]
check("C7 suivi procedure", "loi-2016-16#art-589-nouveau" in ids, str(ids))

print(f"\n{7 - len(fails)}/7 tests passes")
sys.exit(1 if fails else 0)
