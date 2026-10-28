#!/usr/bin/env python3
"""
OCR JuriAgent via Muse Spark vision (Meta Model API).

Les PDF officiels sgg.gouv.bj sont scannes (2013-01: 0 texte extractible,
2017-15: couche OCR illisible). On rend chaque page en PNG (PyMuPDF)
puis transcription exacte par muse-spark-1.3.

Cache par page dans corpus/ocr/<source>/page-XXX.txt -> reprise possible.
Sortie: corpus/ocr/<source>.txt (assemblage) exploitable par ingest.py.

Usage:
  python src/ingest/ocr.py corpus/raw/loi-2013-01.pdf
  python src/ingest/ocr.py corpus/raw/loi-2017-15.pdf --workers 4
Cle lue dans .env (META_API_KEY ou MODEL_API_KEY), jamais affichee.
"""
import argparse
import base64
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROMPT = (
    "Transcris exactement le texte francais de cette page de loi, sans aucun commentaire. "
    "Conserve la numerotation des articles (Article X), les titres de chapitres/sections "
    "et la ponctuation. Si la page est blanche, reponds [PAGE BLANCHE]."
)


def load_key() -> str:
    for env_file in [Path(".env"), Path("../legal-agent-workshop/agent/.env")]:
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                for prefix in ("META_API_KEY=", "MODEL_API_KEY="):
                    if line.startswith(prefix) and len(line) > len(prefix) + 5:
                        return line.split("=", 1)[1].strip()
    key = os.environ.get("META_API_KEY") or os.environ.get("MODEL_API_KEY", "")
    if not key:
        print("ERREUR: aucune cle API (META_API_KEY) trouvee dans .env", file=sys.stderr)
        sys.exit(2)
    return key


def ocr_page(client, model: str, png_bytes: bytes) -> str:
    img = base64.b64encode(png_bytes).decode()
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}},
                ]}],
                max_tokens=3000,
            )
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  retry ({e.__class__.__name__})", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    return ""


def main():
    ap = argparse.ArgumentParser(description="OCR Muse vision")
    ap.add_argument("pdf")
    ap.add_argument("--model", default="muse-spark-1.3")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--pages", default="", help="ex: 1-10 ou vide = tout")
    args = ap.parse_args()

    import fitz  # PyMuPDF
    from openai import OpenAI

    pdf = Path(args.pdf)
    stem = pdf.stem
    cache_dir = Path("corpus/ocr") / stem
    cache_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(str(pdf))
    total = len(doc)
    if args.pages:
        a, b = args.pages.split("-")
        wanted = list(range(int(a), int(b) + 1))
    else:
        wanted = list(range(1, total + 1))
    print(f"{stem}: {total} pages, OCR sur {len(wanted)} pages (workers={args.workers})")

    client = OpenAI(api_key=load_key(), base_url="https://api.meta.ai/v1")

    def work(pno: int) -> tuple[int, int]:
        cache = cache_dir / f"page-{pno:03d}.txt"
        if cache.exists() and cache.stat().st_size > 10:
            return pno, 0
        page = doc[pno - 1]
        png = page.get_pixmap(dpi=args.dpi).tobytes("png")
        text = ocr_page(client, args.model, png)
        cache.write_text(text, encoding="utf-8")
        return pno, len(text)

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(work, p): p for p in wanted}
        for fut in as_completed(futs):
            pno, n = fut.result()
            done += 1
            print(f"[{done}/{len(wanted)}] page {pno} ({n} car.)", flush=True)
    doc.close()

    out = Path("corpus/ocr") / f"{stem}.txt"
    parts = []
    for p in sorted(cache_dir.glob("page-*.txt")):
        parts.append(p.read_text(encoding="utf-8"))
    out.write_text("\n\n".join(parts), encoding="utf-8")
    total_chars = sum(len(x) for x in parts)
    print(f"-> {out} ({len(parts)} pages, {total_chars} car.)")


if __name__ == "__main__":
    main()
