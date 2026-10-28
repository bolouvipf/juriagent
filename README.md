# JuriAgent — Assistant d'information sur le droit foncier au Bénin

> Prototype Meta Global AI Developer Hackathon 2026 — aide anonyme à comprendre sa situation foncière (héritage, titre, expropriation, expulsion, partage) **uniquement à partir des textes officiels**.

**Dépôt public, travail nouveau clairement séparé.** Soumission prévue 3 nov. au soir (deadline 4 nov 21h ET).

## Principes (non négociables — Fiche de route §5)

1. Explique, ne juge pas — jamais de verdict sur culpabilité / chances de gagner
2. Chaque affirmation sourcée (texte, article, date, lien) — pas de source, pas d'affirmation
3. Sait s'abstenir et oriente
4. Tient compte des dates (ex: art. 522-5 — 2 ans dès 2017 → potentiellement périmé)
5. Oriente vers humain (avocat, ANDF, mairie, tribunal)
6. Anonymat — pas de compte, pas de conservation par défaut

## Démarrage rapide

```bash
python -m venv .venv && .\.venv\Scripts\activate  # ou source .venv/bin/activate
pip install -r requirements.txt
python src/ingest/ingest.py --source corpus/raw --out data/ingested/articles.jsonl
python src/api/main.py  # http://localhost:8000
```

## Structure

```
corpus/            # sources officielles — voir corpus/manifest.json (droits)
  raw/             # PDF d'origine (sgg.gouv.bj)
  consolidated/    # 2013-01 consolidé avec modifs 2017-15
data/ingested/     # JSONL par article {text, article, date, modifie_par, lien}
src/
  ingest/          # découpage par article + métadonnées
  search/          # BM25 + sémantique, filtre date/vigueur
  agent/           # questions 3-5 + rédaction format fixe (Muse)
  verifier/        # 2ᵉ passe : chaque affirmation appuyée
  api/             # FastAPI
web/               # page FR, mobile
eval/              # 20 questions §10
```

## Modèles Meta

Rédaction & Vérificateur : `muse-spark-1.3` via `https://api.meta.ai/v1` (clé `LLM_...` — voir `.env.example`). Voix optionnelle : transcription Meta.

## Évaluation (honnête, §10)

20 questions fixées (`eval/questions.json`) : héritage, preuve, expropriation, expulsion, partage + 4 cas d'abstention. Harnais : `python eval/run_eval.py` → `eval/resultats.json`.

**Résultats mesurés (28 oct. 2026, modèles Muse Spark + Wonder) :**
- Abstention conforme : **18/20** (les 2 écarts sont des sur-abstentions : H2, P3 — l'agent refuse par prudence)
- Citations valides : **14/14 réponses** (chaque `[Article X]` existe dans les passages retrouvés)
- Verdicts interdits : **0/20**
- Latence moyenne : ~21 s/question (3 appels modèles + recherche hybride)

Limites connues : la qualité dépend de l'OCR Muse des PDF scannés ; le corpus couvre le code foncier consolidé et 6 décrets de 2015, pas toute la jurisprudence. Ne pas extrapoler au-delà de cet échantillon de 20 questions.

## Licence & droits

Chaque source listée dans `corpus/manifest.json` avec son statut. Ne pas collecter `textes.justice.bj` (accès automatisé refusé) ni LEGIS sans autorisation.

## Historique des commits

Commits incrémentaux — les juges examinent l'historique.
