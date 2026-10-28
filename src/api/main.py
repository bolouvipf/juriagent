#!/usr/bin/env python3
"""
API JuriAgent (FastAPI). Anonyme: aucun compte, aucune conversation stockee.

  GET  /            -> interface web (web/index.html)
  POST /api/ask     -> {question, type, commune, documents, adversaire} => reponse verifiee
  POST /api/export  -> dossier Markdown telechargeable (faits, pieces, questions RDV)
  GET  /api/health
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import FileResponse, PlainTextResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from search.search import Searcher  # noqa: E402
from agent.agent import run as agent_run  # noqa: E402

app = FastAPI(title="JuriAgent — droit foncier Benin")
_searcher: Searcher | None = None


def get_searcher() -> Searcher:
    global _searcher
    if _searcher is None:
        _searcher = Searcher(use_semantic=True)
    return _searcher


class Ask(BaseModel):
    question: str
    type: str = ""
    commune: str = ""
    documents: str = ""
    adversaire: str = ""


class Export(BaseModel):
    question: str
    situation: dict = {}
    reponse: dict = {}


@app.get("/api/health")
def health():
    return {"ok": True, "corpus": len(get_searcher().rows)}


@app.post("/api/ask")
def ask(req: Ask):
    situation = {k: v for k, v in req.model_dump().items() if k != "question" and v}
    return agent_run(req.question, situation, searcher=get_searcher())


@app.post("/api/export")
def export(req: Export):
    r = req.reponse
    lines = ["# Dossier JuriAgent — a apporter a votre rendez-vous", "",
             "**Confidentialite :** ce dossier est genere a partir de ce que vous avez decrit. "
             "N'y ajoutez pas de numeros de piece d'identite ou de titre avant de le partager; "
             "montrez les originaux uniquement a l'avocat ou a l'agent qui vous recoit.", "",
             f"**Votre question :** {req.question}", "",
             "**Votre situation (telle que decrite) :**"]
    for k, v in req.situation.items():
        lines.append(f"- {k} : {v}")
    if r.get("abstention"):
        lines += ["", "L'assistant n'a pas pu repondre a partir des textes officiels disponibles.",
                  "", r.get("orientation", "")]
    else:
        lines += ["", "## Ce que dit la loi"]
        for c in r.get("loi", []):
            lines.append(f"- {c['texte']}")
        lines += ["", "## En mots simples", r.get("simple", ""), "", "## Demarches"]
        lines += [f"- {x}" for x in r.get("demarches", [])]
        lines += ["", "## Pieces a apporter"]
        lines += [f"- {x}" for x in r.get("pieces", [])]
        if r.get("contacts"):
            lines += ["", "## Qui contacter"]
            for c in r["contacts"]:
                lines.append(f"- **{c['qui']}** — {c['role']}. A demander : {c['demander']} ({c['base']})")
        lines += ["", "## Questions a poser lors du rendez-vous",
                  "- Quelles sont les prochaines etapes dans mon cas precis ?",
                  "- Quels delais s'appliquent a ma situation ?",
                  "- Mes documents sont-ils suffisants pour prouver mon droit ?"]
        lines += ["", "## Sources"]
        for s in r.get("sources", []):
            lines.append(f"- Article {s['article']} ({s.get('statut')}): {s.get('lien')}")
    lines += ["", "---", r.get("limite", "")]
    return PlainTextResponse("\n".join(lines), media_type="text/markdown",
                             headers={"Content-Disposition": "attachment; filename=dossier-juriagent.md"})


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
