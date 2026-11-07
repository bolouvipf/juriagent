#!/usr/bin/env python3
"""Build the JuriAgent corpus from OCR page files.

Input : <OCR_DIR>/<doc_id>/pNNN.txt  (one file per page, French OCR)
Output: <OUT>/articles.jsonl, sources.json, qa_report.md, ocr/<doc_id>.txt
"""
import bisect, glob, json, os, re, sys, datetime

OCR_DIR = os.environ.get("OCR_DIR", "/home/claude/ocr")
OUT = os.environ.get("OUT_DIR", "/mnt/user-data/outputs/corpus")
os.makedirs(OUT + "/ocr", exist_ok=True)

DOCS = {
    "loi-2008-07": {
        "title": "Loi n° 2008-07 du 28 février 2011 portant code de procédure civile, commerciale, sociale, administrative et des comptes",
        "short": "Code de procédure civile (2011)",
        "nature": "loi", "date": "2011-02-28", "kind": "base",
        "status": "en_vigueur_texte_origine",
        "status_note": "Texte d'origine de 2011, non consolidé. Beaucoup d'articles ont été remplacés depuis (voir superseded_by).",
        "normative": True,
    },
    "loi-2016-16": {
        "title": "Loi n° 2016-16 du 28 juillet 2016 modifiant et complétant la loi n° 2008-07 du 28 février 2011 portant code de procédure civile, commerciale, sociale, administrative et des comptes",
        "short": "Loi modificative 2016-16",
        "nature": "loi", "date": "2016-07-28", "kind": "modificative",
        "status": "promulguee",
        "status_note": "Promulguée le 28 juillet 2016. Chaque article « nouveau » remplace l'article du même numéro du code de 2011.",
        "normative": True, "modifies": "loi-2008-07",
    },
    "decret-2020-198": {
        "title": "Décret n° 2020-198 du 11 mars 2020 portant transmission à l'Assemblée nationale du projet de loi portant modernisation de la justice",
        "short": "Projet de loi modernisation de la justice (2020)",
        "nature": "decret_et_projet_de_loi", "date": "2020-03-11", "kind": "projet",
        "status": "projet_non_adopte_dans_ce_document",
        "status_note": "PROJET. Le texte joint a une date d'adoption laissée en blanc. Ne jamais citer comme droit en vigueur. Retrouver la loi promulguée.",
        "normative": False,
    },
}

# Target law per draft article of the 2020 project (hard-coded from the text itself)
DRAFT_TARGETS = {"2": "loi-2001-37", "3": "loi-2008-07", "4": "loi-2013-01", "5": "loi-2016-36"}

HDR = re.compile(
    r"^\s*A\S{2,7}e\s+(1er|ler|1[°º][\"'’]?|\d{1,4})\s*(?:[-–.]\s*(\d{1,2}))?\s*"
    r"(nouveau|nouvel|nouvelle|bis|ter)?\s*[:.;]", re.I)
HEAD = re.compile(r"^\s*(LIVRE|TITRE|CHAPITRE|SOUS[- ]?SECTION|SECTION)\b", re.I)
ITEM = re.compile(r"^\s*(\d{1,2})\s?[°º'’\"*o]\s?[-–]\s*")


def load_pages(doc):
    pages = []
    for f in sorted(glob.glob(f"{OCR_DIR}/{doc}/p*.txt")):
        n = int(re.search(r"p(\d+)\.txt", f).group(1))
        pages.append((n, open(f, encoding="utf-8").read()))
    return pages


def clean(ln):
    return re.sub(r"^[|‘’`.,;:~_*•\s]+(?=[A-Za-zÀ-ÿ0-9«\"(])", "", ln.strip())


def is_upper(s):
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and sum(c.isupper() for c in letters) / len(letters) > 0.6


def weird_ratio(text):
    bad = re.findall(r"[^\w\s.,;:'’\"«»()\-–°/%€œŒ!?]", text)
    return len(bad) / max(len(text), 1)


def parse_articles(doc, pages, mode):
    """mode: base | modificative | draft"""
    lines = [(pn, ln) for pn, t in pages for ln in t.splitlines()]
    recs, rejected = [], []
    cur, last, expected = None, 0, 1
    heads = {"livre": "", "titre": "", "chapitre": "", "section": ""}
    i = 0
    forced = {}
    if mode == "base":
        cands = []
        for idx, (pn0, ln0) in enumerate(lines):
            m0 = HDR.match(clean(ln0))
            if m0:
                n0 = 1 if m0.group(1).lower().startswith(("1er", "ler", "1°", "1º")) else int(m0.group(1))
                cands.append((idx, n0, int(m0.group(2) or 0)))
        n = len(cands)
        best, prev = [1] * n, [-1] * n
        for a in range(n):
            for b in range(a):
                if cands[b][1:] < cands[a][1:] and best[b] + 1 > best[a]:
                    best[a], prev[a] = best[b] + 1, b
        keep, k = set(), (max(range(n), key=lambda x: best[x]) if n else -1)
        while k != -1:
            keep.add(k)
            k = prev[k]
        kept_idx = sorted(keep)
        used = {cands[k][1] for k in kept_idx}
        for k in range(n):
            if k in keep:
                forced[cands[k][0]] = (cands[k][1], cands[k][2], False)
                continue
            pos = bisect.bisect(kept_idx, k)
            lo = cands[kept_idx[pos - 1]][1] if pos > 0 else 0
            hi = cands[kept_idx[pos]][1] if pos < len(kept_idx) else 10 ** 9
            gaps = [x for x in range(lo + 1, hi) if x not in used]
            if gaps and not (lo <= cands[k][1] <= hi):
                used.add(gaps[0])
                forced[cands[k][0]] = (gaps[0], 0, True)

    def close():
        nonlocal cur
        if cur:
            cur["text"] = re.sub(r"\n{3,}", "\n\n", "\n".join(cur["_lines"])).strip()
            cur["line_pages"] = cur.pop("_lp"); cur.pop("_lines")
            recs.append(cur)
        cur = None

    while i < len(lines):
        pn, ln = lines[i]
        s = clean(ln)
        if not s:
            if cur:
                cur["_lines"].append(""); cur["_lp"].append(pn)
            i += 1
            continue
        if mode == "base" and HEAD.match(s) and is_upper(s):
            title = s
            j = i + 1
            while j < len(lines) and j <= i + 2 and lines[j][1].strip() and is_upper(lines[j][1].strip()) \
                    and not HEAD.match(lines[j][1].strip()) and not HDR.match(lines[j][1].strip()):
                title += " " + lines[j][1].strip()
                j += 1
            key = HEAD.match(s).group(1).lower().replace("-", "").replace(" ", "")
            key = "section" if key.startswith("sous") or key == "section" else key
            order = ["livre", "titre", "chapitre", "section"]
            if key in order:
                heads[key] = title
                for lower in order[order.index(key) + 1:]:
                    heads[lower] = ""
            i = j
            continue
        m = HDR.match(s)
        accepted = False
        rep_flag = False
        if m:
            num_s, sub, tag = m.group(1), m.group(2), (m.group(3) or "").lower()
            num = 1 if num_s.lower().startswith(("1er", "ler", "1°", "1º")) else int(num_s)
            if mode == "base":
                if i in forced:
                    accepted = True
                    num, subn, rep_flag = forced[i]
                    sub = str(subn) if subn else None
            elif mode == "modificative":
                accepted = bool(tag) or num <= 2
            elif mode == "draft":
                accepted = num in (expected, expected + 1) and not sub
        if accepted:
            close()
            last = max(last, num) if mode == "base" else num
            expected = num + 1
            art = str(num) + (f"-{sub}" if sub else "")
            cur = {"article": art, "tag": tag, "repaired": rep_flag, "page_start": pn, "page_end": pn,
                   "heading_path": " > ".join(v for v in heads.values() if v),
                   "_lines": [s], "_lp": [pn]}
        else:
            if m:
                rejected.append({"page": pn, "line": s[:90]})
            if cur:
                cur["_lines"].append(s); cur["_lp"].append(pn)
                cur["page_end"] = pn
        i += 1
    close()
    return recs, rejected


def split_items(rec):
    """Split draft articles 2 and 3 into numbered modification items."""
    out, cur, last = [], None, 0
    lps = rec.get("line_pages", [])
    for k, ln in enumerate(rec["text"].splitlines()):
        pg = lps[k] if k < len(lps) else rec["page_end"]
        m = ITEM.match(ln)
        if m and int(m.group(1)) in (last, last + 1, last + 2) and int(m.group(1)) > 0 and rec["article"] in DRAFT_TARGETS:
            if cur:
                out.append(cur)
            n = int(m.group(1))
            dup = "-bis" if n == last else ""
            last = n
            cur = {"item": f"{n}{dup}", "lines": [ln], "pages": [pg]}
        elif cur:
            cur["lines"].append(ln); cur["pages"].append(pg)
    if cur:
        out.append(cur)
    return out


def main():
    records, qa, sources = [], [], {}
    for doc, meta in DOCS.items():
        pages = load_pages(doc)
        if not pages:
            qa.append(f"- {doc}: aucune page OCR trouvée.")
            continue
        with open(f"{OUT}/ocr/{doc}.txt", "w", encoding="utf-8") as f:
            for pn, t in pages:
                f.write(f"\n=== PAGE {pn} ===\n{t}")
        sources[doc] = dict(meta, doc_id=doc, pages_ocr=len(pages), source_origin="À RENSEIGNER",
                            rights_status="À VÉRIFIER (ne pas publier le texte tant que non confirmé)")
        base = dict(doc_id=doc, doc_title=meta["title"], doc_date=meta["date"],
                    status=meta["status"], normative=meta["normative"], ocr_clean=False)

        if doc == "decret-2020-198":
            start = next((pn for pn, t in pages if "Assemblée nationale a délibéré" in t or "Assemblee nationale a delibere" in t), None)
            if start is None:
                qa.append("- decret-2020-198: début du projet de loi introuvable.")
                start = 5
            blank = False
            for pn, t in pages:
                m_ad = re.search(r"séance du(.{0,40}?)la loi dont", t, re.S)
                if pn >= start and m_ad and not re.search(r"\d", m_ad.group(1)):
                    blank = True
            sources[doc]["adoption_date_blank"] = blank
            dec_pages = [(pn, t) for pn, t in pages if pn < start]
            records.append(dict(base, id=f"{doc}#decret", article="decret", label="Décret de transmission et exposé des motifs",
                                heading_path="", text="\n".join(t for _, t in dec_pages).strip(),
                                page_start=dec_pages[0][0], page_end=dec_pages[-1][0], normative=False, kind="decret_transmission"))
            recs, rej = parse_articles(doc, [(pn, t) for pn, t in pages if pn >= start], "draft")
            for r in recs:
                tgt = DRAFT_TARGETS.get(r["article"])
                if r["article"] in ("2", "3") and tgt:
                    items = split_items(r)
                    for it in items:
                        txt = "\n".join(it["lines"]).strip()
                        arts = re.findall(r"[Ll]['’]article\s+(\d{1,4})", txt) or re.findall(r"A[a-z]{1,4}cle\s+(\d{1,4})", txt)
                        records.append(dict(base, id=f"{doc}#proj-art{r['article']}-item{it['item']}", article=f"projet-{r['article']}.{it['item']}",
                                            label=f"Projet 2020, article {r['article']}, point {it['item']}", heading_path=r["heading_path"],
                                            text=txt, page_start=min(it["pages"]), page_end=max(it["pages"]), normative=False, kind="projet_item",
                                            proposed_target={"doc_id": tgt, "articles": sorted(set(arts), key=int)[:6], "approximate": True}))
                    if not items:
                        qa.append(f"- decret-2020-198: article {r['article']} du projet non découpé en points.")
                else:
                    records.append(dict(base, id=f"{doc}#proj-art{r['article']}", article=f"projet-{r['article']}",
                                        label=f"Projet 2020, article {r['article']}", heading_path=r["heading_path"],
                                        text=r["text"], page_start=r["page_start"], page_end=r["page_end"], normative=False,
                                        kind="projet_article",
                                        proposed_target=({"doc_id": tgt, "articles": sorted(set(re.findall(r"[Ll]['’]article\s+(\d{1,4})", r["text"])), key=int)[:6], "approximate": True} if tgt else None)))
            nums = [int(r["article"]) for r in recs]
            gaps = [n for n in range(1, max(nums) + 1) if n not in nums] if nums else []
            qa.append(f"- decret-2020-198: {len(recs)} articles du projet; numéros absents dans la séquence: {gaps}; "
                      f"date d'adoption laissée en blanc: {blank}.")
            qa.append(f"  en-têtes rejetés: {len(rej)}")
        else:
            mode = "base" if doc == "loi-2008-07" else "modificative"
            recs, rej = parse_articles(doc, pages, mode)
            for r in recs:
                nouveau = "-nouveau" if r["tag"] == "nouveau" else ""
                rid = f"{doc}#art-{r['article']}{nouveau}"
                rec = dict(base, id=rid, article=r["article"],
                           label=f"Article {r['article']}{' nouveau' if nouveau else ''}",
                           heading_path=r["heading_path"], text=r["text"],
                           page_start=r["page_start"], page_end=r["page_end"], kind=meta["kind"])
                if r.get("repaired"):
                    rec["number_repaired"] = True
                if mode == "modificative" and nouveau:
                    rec["modifies"] = {"doc_id": meta["modifies"], "article": r["article"], "effect": "replace"}
                records.append(rec)
            nums = sorted({int(re.match(r"\d+", r["article"]).group()) for r in recs})
            qa.append(f"- {doc}: {len(recs)} articles; premier={nums[0] if nums else None}, dernier={nums[-1] if nums else None}; "
                      f"en-têtes rejetés (probables références internes): {len(rej)}")
            if mode == "base":
                missing = [n for n in range(1, nums[-1] + 1) if n not in set(nums)]
                qa.append(f"  numéros absents dans la séquence ({len(missing)}): {missing[:60]}{' …' if len(missing) > 60 else ''}")

    # Cross references
    by_base = {}
    for r in records:
        mod = r.get("modifies")
        if mod:
            by_base.setdefault(mod["article"], []).append(r["id"])
    proposed = {}
    for r in records:
        pt = r.get("proposed_target")
        if pt and pt["doc_id"] == "loi-2008-07":
            for a in pt["articles"]:
                proposed.setdefault(a, []).append(r["id"])
    for r in records:
        if r["doc_id"] == "loi-2008-07":
            a = r["article"].split("-")[0]
            r["superseded_by"] = by_base.get(r["article"], []) if "-" not in r["article"] else []
            r["proposed_changes"] = proposed.get(a, [])

    # Check Article 1er list of loi-2016-16 against parsed "nouveau" articles
    first = next((r for r in records if r["doc_id"] == "loi-2016-16" and r["article"] == "1"), None)
    if first:
        listed = {int(n) for n in re.findall(r"\b\d{2,3}\b", first["text"].split("de la loi")[0])}
        found = {int(r["article"]) for r in records if r["doc_id"] == "loi-2016-16" and r.get("modifies")}
        qa.append(f"- loi-2016-16: {len(listed)} articles annoncés dans l'article 1er; {len(found)} trouvés avec « nouveau ». "
                  f"Annoncés mais non trouvés: {sorted(listed - found)}; trouvés mais non annoncés: {sorted(found - listed)}.")

    flagged = [r["id"] for r in records if len(r["text"]) < 40 or weird_ratio(r["text"]) > 0.01 or r.get("number_repaired")]
    for r in records:
        r["needs_review"] = r["id"] in flagged or r.get("number_repaired", False)
    qa.append(f"- Enregistrements à relire (texte très court ou caractères suspects): {len(flagged)} sur {len(records)}.")

    with open(f"{OUT}/articles.jsonl", "w", encoding="utf-8") as f:
        for r in records:
            r.pop("line_pages", None); r.pop("tag", None)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(f"{OUT}/sources.json", "w", encoding="utf-8") as f:
        json.dump(list(sources.values()), f, ensure_ascii=False, indent=2)
    with open(f"{OUT}/qa_report.md", "w", encoding="utf-8") as f:
        f.write(f"# Rapport de contrôle du corpus\n\nGénéré le {datetime.date.today().isoformat()}.\n\n" + "\n".join(qa) + "\n\n"
                "## À relire\n\n" + "\n".join(f"- {x}" for x in flagged[:200]) + "\n")
    print("\n".join(qa))


if __name__ == "__main__":
    main()
