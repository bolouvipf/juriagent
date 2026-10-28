#!/usr/bin/env python3
"""
Recherche hybride JuriAgent sur le corpus consolide (544 articles).

- BM25 (rank-bm25) sur texte normalise (minuscules, sans accents)
- Semantique (sentence-transformers multilingue) si disponible, cache data/index/
- Fusion par rang reciproque (RRF, k=60)
- Filtres: --statut, --modifie (uniquement articles modifies par 2017)

Usage:
  python src/search/search.py "qui peut demander un titre foncier ?"
  python src/search/search.py "expropriation indemnite" --top 5
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CORPUS = Path("corpus/consolidated/articles.jsonl")
CORPUS_EXTRA = [Path("corpus/consolidated/decrets.jsonl")]
INDEX_DIR = Path("data/index")
EMB_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def normalize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", text)


class Searcher:
    """BM25 uniquement. Aucun modele non-Meta a l'execution (regle hackathon):
    la pertinence semantique est assuree en amont par la reformulation Muse
    et en aval par le re-classement Muse dans l'agent."""

    def __init__(self, corpus: Path = CORPUS, use_semantic: bool = False):
        self.rows = [json.loads(l) for l in corpus.read_text(encoding="utf-8").splitlines() if l.strip()]
        for extra in CORPUS_EXTRA:
            if extra.exists():
                self.rows += [json.loads(l) for l in extra.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.tokens = [normalize(r["texte"]) for r in self.rows]
        from rank_bm25 import BM25Okapi
        self.bm25 = BM25Okapi(self.tokens)
        self.embeddings = None
        self.model = None

    def search(self, query: str, top_k: int = 5, statut: str | None = None, modifie: bool = False) -> list[dict]:
        import numpy as np
        qtokens = normalize(query)
        bm25_scores = self.bm25.get_scores(qtokens)
        order_bm25 = np.argsort(-bm25_scores)
        ranks: dict[int, float] = {}
        for rank, idx in enumerate(order_bm25):
            ranks[int(idx)] = ranks.get(int(idx), 0.0) + 1.0 / (60 + rank + 1)
        if self.embeddings is not None and self.model is not None:
            qemb = self.model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0]
            sims = self.embeddings @ qemb
            for rank, idx in enumerate(np.argsort(-sims)):
                ranks[int(idx)] = ranks.get(int(idx), 0.0) + 1.0 / (60 + rank + 1)
        results = []
        for idx, score in sorted(ranks.items(), key=lambda kv: -kv[1]):
            r = self.rows[idx]
            if statut and r.get("statut") != statut:
                continue
            if modifie and not r.get("modifie_par"):
                continue
            results.append({
                "id": r["id"], "article": r["article"], "score": round(float(score), 5),
                "statut": r.get("statut"), "modifie_par": r.get("modifie_par"),
                "lien_source": r.get("lien_source"),
                "extrait": r["texte"][:600],
            })
            if len(results) >= top_k:
                break
        return results


def main():
    ap = argparse.ArgumentParser(description="Recherche hybride JuriAgent")
    ap.add_argument("query")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--statut", default=None)
    ap.add_argument("--modifie", action="store_true", help="uniquement articles modifies par 2017")
    ap.add_argument("--no-semantic", action="store_true")
    args = ap.parse_args()
    s = Searcher(use_semantic=not args.no_semantic)
    for r in s.search(args.query, top_k=args.top, statut=args.statut, modifie=args.modifie):
        print(f"[{r['score']}] Article {r['article']} ({r['statut']}) {r['lien_source'] or ''}")
        print("   ", r["extrait"][:220].replace("\n", " "), "...")


if __name__ == "__main__":
    main()
