#!/usr/bin/env python3
"""
Reponse deterministe (sans LLM) sur le corpus de procedure civile.
Regles INTEGRATION R1-R5: statut respecte, version recente, citation avec
page, abstention sur lacune/needs_review/couverture, aucun verdict (T5).
Le LLM, s'il est branche ensuite, ne recoit que les `normative` ci-dessous
et le verificateur controle chaque phrase citee (R-verificateur).
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from search.procedure import ProcedureCorpus, PROJET_LABEL  # noqa: E402

ORIENTATION = ("Pour un avis sur votre situation precise, consultez un avocat "
               "ou le greffe du tribunal competent.")
VERDICT = re.compile(r"gagner|perdre|qui a raison|mes chances|coupable|verdict",
                     re.IGNORECASE)


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def answer(corpus: ProcedureCorpus, question: str) -> dict:
    if VERDICT.search(_fold(question)):
        return {"abstention": True, "raison": "prediction_verdict",
                "message": "Je ne peux pas predire l'issue d'un proces ni dire qui a raison. "
                           + ORIENTATION,
                "citations": [], "projet": []}
    res = corpus.search(question)
    if res["couverture_manquante"]:  # R5 / T6
        return {"abstention": True, "raison": "texte_de_base_pas_encore_integre",
                "message": ("Texte de base pas encore integre: ce corpus contient le code de "
                            "procedure civile, pas le code foncier et domanial "
                            f"({', '.join(res['couverture_manquante'])}). Rien n'est deduit "
                            "du code de procedure. " + ORIENTATION),
                "citations": [], "projet": []}
    if res["lacune"]:  # T4: aveu de lacune, aucune invention
        return {"abstention": True, "raison": "lacune_corpus",
                "message": res["lacune"] + " " + ORIENTATION,
                "citations": [], "projet": []}
    norm = res["normative"]
    if not norm:
        return {"abstention": True, "raison": "aucun_id_pertinent",
                "message": "Aucun texte pertinent trouve dans le corpus. " + ORIENTATION,
                "citations": [], "projet": []}
    top = norm[0]["record"]
    # R4: sens dependant d'un chiffre/delai + needs_review -> abstention ciblee
    if top.get("needs_review"):
        return {"abstention": True, "raison": "needs_review",
                "message": (f"{norm[0]['citation_text']}: enregistrement signale a relire "
                            "(texte OCR incertain); je ne peux pas affirmer son contenu, "
                            "notamment s'il porte un delai. " + ORIENTATION),
                "citations": [norm[0]["citation"]], "projet": []}
    return {
        "abstention": False,
        "loi": [{"id": e["record"]["id"], "texte": e["record"]["text"][:1200],
                 "citation": e["citation_text"]} for e in norm],
        "citations": [e["citation"] for e in norm],
        # R1: projet jamais melange aux regles en vigueur
        "projet": [{"id": e["record"]["id"], "encadre": PROJET_LABEL,
                    "citation": e["citation_text"]} for e in res["projet"]],
        "orientation": ORIENTATION,
    }
