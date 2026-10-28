#!/usr/bin/env python3
"""
Consolidation JuriAgent: loi 2013-01 (base) + loi 2017-15 (modificative).

Regle d'or (Fiche sec.7): ne jamais travailler sur la loi modificative seule.
- article supprime par 2017 art.1er -> retire
- article remplace ("Article X nouveau") -> texte 2017, modifie_par=loi-2017-15
- article inchange -> texte 2013

Entree: data/ingested/articles.jsonl
Sortie: corpus/consolidated/articles.jsonl
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SRC = Path("data/ingested/articles.jsonl")
OUT = Path("corpus/consolidated/articles.jsonl")


def norm(num: str) -> str:
    return re.sub(r"\s+", "", str(num).lower())


def main():
    rows = [json.loads(l) for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    base = {norm(r["article"]): r for r in rows if r["source_id"] == "loi-2013-01"}
    mods = {norm(r["article"]): r for r in rows if r["source_id"] == "loi-2017-15"}
    print(f"base 2013: {len(base)} | modifs 2017: {len(mods)}")

    # Articles supprimes: lus dans le texte de l'art. 1er de 2017 ("les articles 16 et 501")
    deleted = set()
    art1 = mods.get("1er") or mods.get("1")
    if art1:
        m = re.search(r"articles?\s+([\d,\s et]+?)\s+de la loi", art1["texte"], re.IGNORECASE)
        if m:
            deleted = {norm(x) for x in re.findall(r"\d+", m.group(1))}
    if not deleted:
        deleted = {"16", "501"}
    print(f"supprimes: {sorted(deleted)}")

    meta = {"1er", "1", "2"}  # articles propres a la loi modificative (suppression + liste)
    consolidated = []
    replaced = added = 0
    for num, rec in base.items():
        if num in deleted:
            continue
        if num in mods and num not in meta:
            m = mods[num]
            consolidated.append({
                **m,
                "id": f"loi-2013-01_art_{num}",
                "source_id": "loi-2013-01-consolide",
                "date_adoption": "2013-08-14",
                "modifie_par": "loi-2017-15 (2017-08-10)",
                "lien_source": "https://sgg.gouv.bj/doc/loi-2017-15/",
                "statut": "modifie",
            })
            replaced += 1
        else:
            consolidated.append({**rec, "source_id": "loi-2013-01-consolide", "statut": "en vigueur (2013)"})
    for num, rec in mods.items():
        if num in meta or num in base:
            continue
        consolidated.append({
            **rec,
            "id": f"loi-2013-01_art_{num}",
            "source_id": "loi-2013-01-consolide",
            "date_adoption": "2017-08-10",
            "modifie_par": None,
            "statut": "ajoute par loi-2017-15",
        })
        added += 1

    def sort_key(r):
        m = re.match(r"(\d+)", r["article"])
        return (int(m.group(1)) if m else 9999, r["article"])

    consolidated.sort(key=sort_key)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in consolidated:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"-> {OUT}: {len(consolidated)} articles (remplaces={replaced}, ajoutes={added}, supprimes={len(deleted)})")


if __name__ == "__main__":
    main()
