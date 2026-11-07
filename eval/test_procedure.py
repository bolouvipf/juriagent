#!/usr/bin/env python3
"""Tests d'acceptation INTEGRATION section 6 (T1-T7) — verifient les id, pas
le contenu juridique. Sans LLM, sans reseau.
Usage: python eval/test_procedure.py  (sortie !=0 si un test echoue)"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from search.procedure import ProcedureCorpus  # noqa: E402
from agent.procedure_agent import answer  # noqa: E402

c = ProcedureCorpus()
fails = []


def check(name, cond, detail=""):
    print(("OK  " if cond else "FAIL") + f" {name} {detail}")
    if not cond:
        fails.append(name)


def ids(res, key="loi"):
    return [x["id"] for x in res.get(key, [])]


# T1: version 2016-16 servie, pas l'originale 2011 remplacee
r = answer(c, "Quel est le delai d'appel en matiere contentieuse ?")
check("T1", "loi-2016-16#art-621-nouveau" in ids(r) and "loi-2008-07#art-621" not in ids(r), str(ids(r)))

# T2: le projet 2020 n'apparait que dans l'encadre projet, jamais en loi
r = answer(c, "Comment faire appel d'une decision en matiere fonciere ?")
check("T2", all(not i.startswith("decret-2020-198") for i in ids(r))
      and all(p.get("encadre") for p in r.get("projet", [])), str(ids(r)))

# T3: 589 nouveau + mention proposed_changes dans la citation
r = answer(c, "Delai d'appel contre le juge de l'execution")
cit = " ".join(x.get("citation", "") for x in r.get("loi", []))
check("T3", "loi-2016-16#art-589-nouveau" in ids(r) and "projet de 2020" in cit.lower(), str(ids(r)))

# T4: article 884 nouveau = page manquante -> aveu de lacune, aucune invention
r = answer(c, "Que dit l'article 884 ?")
check("T4", r.get("abstention") and r.get("raison") == "lacune_corpus" and not r.get("loi"), r.get("raison", ""))

# T5: refus de predire
r = answer(c, "Vais-je gagner mon proces ?")
check("T5", r.get("abstention") and r.get("raison") == "prediction_verdict", r.get("raison", ""))

# T6: couverture fonciere absente de ce corpus
r = answer(c, "Mon voisin a pris une partie de mon terrain, quel est mon titre ?")
check("T6", r.get("abstention") and r.get("raison") == "texte_de_base_pas_encore_integre", r.get("raison", ""))

# T7: toute reponse non-abstention contient label, date, pages, badge statut
r = answer(c, "Quel est le delai d'appel en matiere contentieuse ?")
ok = bool(r.get("citations")) and all(
    x.get("label") and x.get("doc_date") and "p." in x.get("pages_pdf", "") and x.get("badge")
    for x in r["citations"])
check("T7", ok, str(r.get("citations", [{}])[0]))

print(f"\n{7 - len(fails)}/7 tests passes")
sys.exit(1 if fails else 0)
