#!/usr/bin/env python3
"""
Evaluation JuriAgent sur les 20 questions figees (eval/questions.json).

Mesures (fiche sec.10):
- citations: chaque [Article X] cite existe parmi les passages retrouves
- abstention conforme a l'attente
- aucun verdict/strategie (regex interdite) dans la reponse finale
- latence par question
Resultats bruts: eval/resultats.json (+ resume console honnete, sans extrapolation).
"""
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from search.search import Searcher          # noqa: E402
from agent.agent import run                 # noqa: E402
from verifier.verifier import FORBIDDEN, CITATION  # noqa: E402


def main():
    questions = json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
    searcher = Searcher(use_semantic=True)
    results = []
    for q in questions:
        t0 = time.time()
        situation = {k: q[k] for k in ("type", "commune", "documents", "adversaire") if q.get(k)}
        try:
            ans = run(q["question"], situation, searcher=searcher)
        except Exception as e:
            ans = {"erreur": f"{e.__class__.__name__}: {e}"}
        dt = round(time.time() - t0, 1)
        text = json.dumps(ans, ensure_ascii=False)
        cited = CITATION.findall(text)
        known = {str(s["article"] if isinstance(s, dict) else s).lower() for s in ans.get("sources", [])}
        citations_ok = all(c.lower() in known for c in cited) if cited else (not ans.get("loi"))
        abst = bool(ans.get("abstention"))
        verdict = bool(FORBIDDEN.search(text)) and not abst
        row = {"id": q["id"], "categorie": q["categorie"], "abstention": abst,
               "abstention_attendue": q["abstention_attendue"], "abstention_ok": abst == q["abstention_attendue"],
               "citations": cited, "citations_ok": citations_ok, "verdict_interdit": verdict,
               "nb_affirmations": len(ans.get("loi", [])), "secondes": dt}
        results.append(row)
        print(f"{q['id']} [{q['categorie']}] abst={abst} (attendu {q['abstention_attendue']}) "
              f"citations_ok={citations_ok} verdict={verdict} {dt}s", flush=True)
    n = len(results)
    answered = [r for r in results if not r["abstention"]]
    summary = {
        "total": n,
        "abstention_conforme": f"{sum(r['abstention_ok'] for r in results)}/{n}",
        "citations_valides": f"{sum(r['citations_ok'] for r in answered)}/{len(answered)} reponses",
        "verdicts_interdits": sum(r["verdict_interdit"] for r in results),
        "latence_moyenne_s": round(sum(r["secondes"] for r in results) / n, 1),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    (ROOT / "eval" / "resultats.json").write_text(
        json.dumps({"resume": summary, "details": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("-> eval/resultats.json")


if __name__ == "__main__":
    main()
