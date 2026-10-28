#!/usr/bin/env python3
"""
Ingestion JuriAgent — découpage par article avec métadonnées.

Entrée:  corpus/raw/*.pdf (ou .txt) + corpus/manifest.json
Sortie:  data/ingested/articles.jsonl  (une ligne = un article)

Chaque ligne JSON:
{
  "id": "loi-2013-01_art_12",
  "source_id": "loi-2013-01",
  "article": "12",
  "texte": "...",
  "date_adoption": "2013-08-14",
  "modifie_par": null,
  "lien_source": "https://sgg.gouv.bj/...",
  "pages": [3,4],
  "char_count": 1234
}

Usage:
  python src/ingest/ingest.py --source corpus/raw --out data/ingested/articles.jsonl
  python src/ingest/ingest.py --source corpus/raw/loi-2017-15.pdf --out data/ingested/articles.jsonl
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Article pattern: "Article 12", "Article  12.", "Art. 12", "ARTICLE 12 :"
ARTICLE_RE = re.compile(r'(?:^|\n)\s*(?:Article|Art\.)\s+(\d+(?:\s*[-bis|ter]*)?)\s*[:.\-–]?\s*', re.IGNORECASE)

def extract_text_from_pdf(pdf_path: Path) -> list[tuple[int, str]]:
    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf manquant: pip install pypdf", file=sys.stderr)
        sys.exit(1)
    reader = PdfReader(str(pdf_path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        pages.append((i, txt))
    return pages

def extract_text_from_txt(txt_path: Path) -> list[tuple[int, str]]:
    return [(1, txt_path.read_text(encoding="utf-8", errors="ignore"))]

def split_by_article(full_text: str) -> list[tuple[str, str]]:
    """Retourne [(numero, texte_article), ...]. Si aucun Article trouvé, retourne un seul morceau 'preambule'."""
    matches = list(ARTICLE_RE.finditer(full_text))
    if not matches:
        cleaned = full_text.strip()
        return [("preambule", cleaned)] if cleaned else []
    articles = []
    for idx, m in enumerate(matches):
        num = re.sub(r'\s+', '', m.group(1).lower())  # "12 bis" -> "12bis"
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        body = full_text[start:end].strip()
        # inclure l'en-tête "Article X" dans le texte pour le contexte
        header = f"Article {m.group(1).strip()}"
        articles.append((num, f"{header}\n{body}".strip()))
    return articles

def load_manifest(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        return {}
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {e["id"]: e for e in data}

def ingest_file(file_path: Path, manifest_entry: dict | None) -> list[dict]:
    if file_path.suffix.lower() == ".pdf":
        pages = extract_text_from_pdf(file_path)
    elif file_path.suffix.lower() in (".txt", ".md"):
        pages = extract_text_from_txt(file_path)
    else:
        return []
    # concat avec marqueurs de page pour pouvoir retrouver pages par article
    # on garde pages séparées puis on mapping article -> pages en cherchant le texte
    full_text = "\n".join(t for _, t in pages)
    if len(full_text.strip()) < 100:
        # PDF scanne — pypdf ne sort rien, OCR requis
        print(f"WARN {file_path.name}: texte extrait vide ({len(full_text)} car) — PDF scanne, OCR requis", file=sys.stderr)
        full_text = ""
    articles = split_by_article(full_text)
    if not articles and not full_text.strip():
        # placeholder pour tracer le fichier scanne
        doc_id = manifest_entry["id"] if manifest_entry else file_path.stem
        return [{"id": f"{doc_id}_scanne", "source_id": doc_id, "article": "SCANNE", "texte": "[[PDF scanne — OCR requis]]", "date_adoption": manifest_entry.get("date_adoption") if manifest_entry else None, "modifie_par": None, "lien_source": manifest_entry.get("source_url") if manifest_entry else None, "pages": [1], "char_count": 0, "needs_ocr": True}]

    # mapping simple: pour chaque article, on cherche sur quelles pages son texte apparaît
    out = []
    for num, texte in articles:
        # pages contenant ce morceau (heuristique: substring)
        snippet = texte[:120].strip()
        page_nums = [p for p, t in pages if snippet and snippet[:60] in t] or [pages[0][0] if pages else 1]
        # fallback: si preambule sans numéro, page 1
        doc_id = manifest_entry["id"] if manifest_entry else file_path.stem
        rec = {
            "id": f"{doc_id}_art_{num}",
            "source_id": doc_id,
            "article": num,
            "texte": texte,
            "date_adoption": manifest_entry.get("date_adoption") if manifest_entry else None,
            "modifie_par": manifest_entry.get("modifie_par") if manifest_entry else None,
            "lien_source": manifest_entry.get("source_url") if manifest_entry else None,
            "pages": page_nums[:3],
            "char_count": len(texte),
        }
        out.append(rec)
    return out

def main():
    ap = argparse.ArgumentParser(description="Ingestion par article")
    ap.add_argument("--source", required=True, help="dossier ou fichier (corpus/raw)")
    ap.add_argument("--out", required=True, help="fichier JSONL de sortie")
    ap.add_argument("--manifest", default="corpus/manifest.json", help="chemin manifest")
    ap.add_argument("--clear", action="store_true", help="écrase le fichier de sortie (défaut: append)")
    args = ap.parse_args()

    source = Path(args.source)
    out_path = Path(args.out)
    manifest = load_manifest(Path(args.manifest))

    # collecter fichiers
    files: list[Path] = []
    if source.is_file():
        files = [source]
    elif source.is_dir():
        files = sorted([p for p in source.rglob("*") if p.suffix.lower() in (".pdf", ".txt", ".md") and p.is_file()])
    else:
        print(f"source introuvable: {source}", file=sys.stderr)
        sys.exit(2)

    if not files:
        print(f"aucun fichier .pdf/.txt dans {source}", file=sys.stderr)
        sys.exit(2)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if args.clear or not out_path.exists() else "w"  # on écrase à chaque run complet
    # Pour un run complet depuis un dossier, on écrase

    all_records: list[dict] = []
    for f in files:
        # trouver l'entrée manifest la plus proche (par local_path)
        entry = None
        for mid, m in manifest.items():
            lp = m.get("local_path", "")
            if lp and (f.name in lp or mid in f.stem.lower()):
                entry = m
                break
        # fallback: si un seul fichier et pas de match, prendre le premier
        recs = ingest_file(f, entry)
        print(f"{f.name}: {len(recs)} articles")
        all_records.extend(recs)

    with out_path.open("w", encoding="utf-8") as out:
        for r in all_records:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"-> {len(all_records)} articles ecrits dans {out_path}")
    # petit controle: afficher les 3 premiers ids
    for r in all_records[:3]:
        print(f"  - {r['id']} ({r['char_count']} car.)")
    if any("preambule" in r["article"] or r["char_count"] < 50 for r in all_records):
        print("NOTE: certains fichiers sont scannes (texte vide) -> OCR necessaire (voir TODO)", file=sys.stderr)

if __name__ == "__main__":
    main()
