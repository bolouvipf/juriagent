#!/usr/bin/env python3
"""
Corpus de procedure civile (docs/INTEGRATION-procedure.md, regles R1-R6).

- Chargeur: corpus/articles.jsonl + corpus/sources.json, refuse un
  enregistrement sans `status` (R-chargeur). Chemin surchargeable par
  JURI_PROCEDURE_CORPUS (stockage prive, R6: articles.jsonl non versionne).
- Recherche: BM25 sur heading_path+label+text normalise + trigrammes
  (absorbe les erreurs OCR type "Aticle"/"oppel"). Aucun embedding.
- R1: seuls normative=True = "ce que dit la loi"; projet_* /
  decret_transmission -> encadre separe, jamais regle en vigueur.
- R2: superseded_by -> renvoie le remplacant ("version loi 2016-16");
  proposed_changes -> mention "projet 2020, verifier adoption".
- R3: citation = label + titre court + doc_date + pages PDF + badge statut
  + avertissement OCR.
- R4/R5: lacunes connues et coverage_check (foncier de base absent de CE
  corpus -> ne rien deduire du code de procedure).
"""
import json
import os
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = ROOT / "corpus" / "articles.jsonl"
SOURCES = ROOT / "corpus" / "sources.json"
OCR_WARNING = "Texte issu d'une reconnaissance automatique : verifier sur le document officiel"
PROJET_LABEL = "Projet de loi (2020) : non confirme comme adopte"

# INTEGRATION section 5: page imprimee 15 manquante dans le PDF 2016-16.
MISSING_2016 = {"874", "883", "884", "886", "888", "894"}
PARTIAL_2016 = {"881"}  # fin manquante
MISSING_2011 = {143, 144, 301, 311, 375, 402, 427, 445, 466, 524, 534, 684, 711,
                801, 809, 1040, 1043, 1048, 1053, 1062, 1121, 1157, 1180, 1181,
                1193, 1200, 1210, 1219, 1220, 1230}

FONCIER_KEYWORDS = ("titre foncier", "terrain", "heritage", "succession",
                    "expropriation", "propriete fonciere", "partage foncier",
                    "voisin a pris", "mon terrain", "parcelle")
# Textes fonciers de base NON presents dans ce corpus de procedure (R5).
FONCIER_REQUIRED = ["loi-2013-01", "loi-2017-15"]


def normalize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", text)


def _trigrams(tokens: list[str]) -> set[str]:
    out = set()
    for t in tokens:
        p = f"  {t} "
        out.update(p[i:i + 3] for i in range(len(p) - 2))
    return out


class ProcedureCorpus:
    def __init__(self, corpus: Path | None = None, sources: Path = SOURCES):
        path = corpus or Path(os.environ.get("JURI_PROCEDURE_CORPUS", DEFAULT_CORPUS))
        if not path.exists():
            raise FileNotFoundError(
                f"Corpus procedure introuvable: {path} (R6: stockage prive, "
                "definir JURI_PROCEDURE_CORPUS)")
        self.sources = {}
        if sources.exists():
            for s in json.loads(sources.read_text(encoding="utf-8")):
                self.sources[s["doc_id"]] = s
        self.rows, self.by_id = [], {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if not r.get("status") or not r.get("id"):
                raise ValueError(f"Enregistrement refuse (status/id manquant): {r.get('id')!r}")
            self.rows.append(r)
            self.by_id[r["id"]] = r
        # INTEGRATION 4.4 + R2: le projet 2020 vise des articles par
        # proposed_target (approximate) et par "Article N :" cites dans les
        # gros items (ex. item17 cite 583..604 dont 589). On en derive
        # l'ensemble des numeros vises, sans reecrire le corpus stocke.
        self._proposed_articles: set[str] = set()
        for r in self.rows:
            for a in (r.get("proposed_target") or {}).get("articles", []):
                self._proposed_articles.add(str(a))
            if r.get("kind", "").startswith("projet"):
                self._proposed_articles.update(
                    re.findall(r"Article\s+(\d+)\s*:", r.get("text", "")))
            if r.get("proposed_changes"):
                self._proposed_articles.add(str(r.get("article")))
        from rank_bm25 import BM25Okapi
        self._tokens = [normalize(f"{r.get('heading_path','')} {r.get('label','')} {r.get('text','')}")
                        for r in self.rows]
        self._tri = [_trigrams(t) for t in self._tokens]
        self.bm25 = BM25Okapi(self._tokens)

    # --- R2: resolution de version -------------------------------------
    def resolve(self, row: dict) -> tuple[dict, str | None]:
        """Suit superseded_by jusqu'a la version en vigueur."""
        seen, note = set(), None
        while row.get("superseded_by") and row["id"] not in seen:
            seen.add(row["id"])
            nxt = self.by_id.get(row["superseded_by"][0])
            if nxt is None:
                break
            row, note = nxt, "version loi 2016-16"
        return row, note

    # --- R3: citation ---------------------------------------------------
    def citation(self, row: dict, version_note: str | None = None) -> dict:
        src = self.sources.get(row["doc_id"], {})
        c = {
            "id": row["id"],
            "label": row.get("label"),
            "doc_title_short": src.get("short", row.get("doc_title", "")),
            "doc_date": row.get("doc_date"),
            "pages_pdf": f"p. {row.get('page_start')}-{row.get('page_end')} du PDF",
            "status": row.get("status"),
            "badge": row.get("status"),
            "ocr_warning": OCR_WARNING,
        }
        if version_note:
            c["version"] = version_note
        if row.get("proposed_changes") or (
                row.get("normative") and str(row.get("article")) in self._proposed_articles):
            c["projet_2020"] = ("Un projet de 2020 propose de le modifier ; "
                                "verifier s'il a ete adopte")
        return c

    def format_citation(self, row: dict, version_note: str | None = None) -> str:
        c = self.citation(row, version_note)
        s = (f"{c['label']} — {c['doc_title_short']} ({c['doc_date']}), "
             f"{c['pages_pdf']} [{c['badge']}]")
        if version_note:
            s += f" — {version_note}"
        if c.get("projet_2020"):
            s += f" — {c['projet_2020']}"
        return s + f" — {OCR_WARNING}"

    # --- R5: couverture -------------------------------------------------
    def coverage_check(self, question: str) -> list[str]:
        q = " ".join(normalize(question))
        if any(k in q for k in FONCIER_KEYWORDS):
            return [d for d in FONCIER_REQUIRED if d not in
                    {r["doc_id"] for r in self.rows}]
        return []

    def gap_for(self, question: str) -> str | None:
        """Article explicitement demande mais absent du PDF fourni (T4)."""
        m = re.search(r"article\s+(\d+)", " ".join(normalize(question)))
        if not m:
            return None
        n = m.group(1)
        if n in MISSING_2016:
            return (f"L'article {n} nouveau (loi 2016-16) est absent du corpus: "
                    "page imprimee 15 manquante dans le PDF fourni (16 pages). "
                    "Obtenir une copie complete; en attendant, aucun contenu affirme.")
        if n in PARTIAL_2016:
            return (f"L'article {n}: fin manquante (page imprimee 15 absente du "
                    "PDF 2016-16 fourni). Contenu partiel, a verifier.")
        if int(n) in MISSING_2011:
            return (f"L'article {n} du code de 2011 n'a pas ete retrouve par la "
                    "reconnaissance automatique. Ne pas conclure qu'il n'existe pas.")
        return None

    # --- Recherche + R1/R2 ----------------------------------------------
    def search(self, query: str, top_k: int = 5) -> dict:
        import numpy as np
        qt = normalize(query)
        scores = self.bm25.get_scores(qt)
        qtri = _trigrams(qt)
        if qtri:  # bonus trigrammes: absorbe "Aticle", "oppel"...
            for i, tri in enumerate(self._tri):
                scores[i] += 0.3 * len(qtri & tri) / len(qtri)
        out_norm, out_projet, seen = [], [], set()
        for idx in np.argsort(-scores):
            if scores[idx] <= 0:
                break
            row, note = self.resolve(self.rows[int(idx)])
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            entry = {"record": row, "score": round(float(scores[idx]), 3),
                     "citation": self.citation(row, note),
                     "citation_text": self.format_citation(row, note)}
            if row.get("normative") and row.get("kind") not in ("projet_article", "projet_item", "decret_transmission"):
                out_norm.append(entry)
            else:  # R1: encadre projet separe
                entry["encadre"] = PROJET_LABEL
                out_projet.append(entry)
            if len(out_norm) >= top_k and len(out_projet) >= 3:
                break
        return {"normative": out_norm[:top_k], "projet": out_projet[:3],
                "lacune": self.gap_for(query),
                "couverture_manquante": self.coverage_check(query)}
