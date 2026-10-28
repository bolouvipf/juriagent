#!/usr/bin/env python3
"""
Verificateur JuriAgent: controle deterministe + modele.

1. Deterministe: chaque citation [Article X] existe dans les passages fournis;
   phrases interdites (verdict/strategie) supprimees par regex.
2. Modele (Muse Spark, appel separe): chaque affirmation est-elle appuyee par un passage cite?
   Retourne les indices soutenus; le reste est retire (abstention partielle).
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORBIDDEN = re.compile(
    r"(coupable|vous avez (gain de cause|raison)|vous (allez )?gagnerez|il faut (attaquer|saisir)|"
    r"je vous conseille de (porter plainte|faire appel))", re.IGNORECASE)
CITATION = re.compile(r"\[Article\s+([0-9]+[a-z]*)\]", re.IGNORECASE)


def deterministic_filter(claims: list[dict], passages: list[dict]) -> list[dict]:
    known = {str(p["article"]).lower() for p in passages}
    kept = []
    for c in claims:
        if FORBIDDEN.search(c.get("texte", "")):
            continue
        cites = CITATION.findall(c.get("texte", ""))
        if cites and not all(x.lower() in known for x in cites):
            continue
        kept.append(c)
    return kept


def model_check(client, model: str, claims: list[dict], passages: list[dict]) -> list[dict]:
    if not claims:
        return []
    corpus = "\n\n".join(f"[Article {p['article']}] {p['texte'][:1500]}" for p in passages)
    listing = "\n".join(f"{i}. {c['texte']}" for i, c in enumerate(claims))
    prompt = (
        "Tu es un verificateur juridique strict. Pour chaque affirmation numerotee, dis si elle est "
        "directement appuyee par les passages du code foncier beninois ci-dessous. Reponds UNIQUEMENT "
        "en JSON: {\"soutenues\": [indices], \"non_soutenues\": [indices]}.\n\n"
        f"PASSAGES:\n{corpus}\n\nAFFIRMATIONS:\n{listing}"
    )
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=6000, temperature=0,
        )
        raw = r.choices[0].message.content or "{}"
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        verdict = json.loads(m.group(0)) if m else {}
        ok = set(verdict.get("soutenues", []))
        return [c for i, c in enumerate(claims) if i in ok]
    except Exception as e:
        print(f"verificateur modele indisponible ({e.__class__.__name__}), filtre deterministe seul", file=sys.stderr)
        return claims


DEADLINE_HINT = re.compile(r"(deux|2)\s*(ans|annees)|avant le|au plus tard|delai de", re.IGNORECASE)


def deadline_warnings(passages: list[dict]) -> list[str]:
    out = []
    for p in passages:
        if DEADLINE_HINT.search(p["texte"]):
            out.append(f"Article {p['article']}: mentionne un delai — verifier sa validite a ce jour (texte de {p.get('date_adoption') or 'date inconnue'}).")
    return out[:3]
