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

**Tous les modèles appelés à l'exécution sont des modèles Meta** (règle du hackathon vérifiée le 28/10/2026) : OCR des PDF scannés, reformulation des questions, re-classement des passages, rédaction et vérification séparée — `muse-spark-1.3` via `https://api.meta.ai/v1` (clé `LLM_...` — voir `.env.example`). La recherche lexicale est BM25 (algorithme, pas un modèle). *Historique : un modèle d'embeddings HuggingFace non-Meta a été testé puis retiré du projet le 28/10 pour conformité.*

## Logiciels open source et données publiques

- Logiciels : FastAPI, Uvicorn, rank-bm25, pypdf, PyMuPDF, OpenAI SDK (client compatible API Meta) — licences respectées, voir `requirements.txt`.
- Données publiques : textes officiels béninois téléchargés sur le site du Secrétariat Général du Gouvernement (sgg.gouv.bj) et listés dans `corpus/manifest.json` avec leur source. Aucune donnée sans droits n'est incluse (LEGIS et textes.justice.bj exclus).

## Évaluation (honnête, §10)

20 questions fixées (`eval/questions.json`) : héritage, preuve, expropriation, expulsion, partage + 4 cas d'abstention. Harnais : `python eval/run_eval.py` → `eval/resultats.json`.

**Résultats mesurés (28 oct. 2026, modèles Muse Spark (redaction + verification separee)) :**
- Abstention conforme : **18/20** (les 2 écarts sont des sur-abstentions : H2, P3 — l'agent refuse par prudence)
- Citations valides : **18/18 réponses** (chaque `[Article X]` existe dans les passages retrouvés)
- Verdicts interdits : **0/20**
- Latence moyenne : ~30 s/question (reformulation + re-classement + rédaction + vérification, tous Muse Spark)

**Comparaison des deux inférences Meta (même agent, même corpus, 28 oct. 2026) :**

| Fournisseur | Modèle | Abstention conforme | Citations valides | Verdicts interdits | Latence moy. |
|---|---|---|---|---|---|
| API Meta (production) | muse-spark-1.3 | **18/20** | 18/18 | **0** | 29,6 s |
| Baseten (crédits hackathon) | muse-spark-open-1026 (open-weights) | 17/20 | 17/17 | 1 (S2) + A2/A4 non-abstentions | 23,5 s |

Choix : la production reste sur l'API Meta (priorité à la sécurité juridique : aucun verdict). Baseten reste disponible via `JURI_MODEL_PROVIDER=baseten` (secours / comparaison). Détails : `eval/resultats.json` et `eval/resultats-baseten.json`.

Limites connues : la qualité dépend de l'OCR Muse des PDF scannés ; le corpus couvre le code foncier consolidé et 6 décrets de 2015, pas toute la jurisprudence. Ne pas extrapoler au-delà de cet échantillon de 20 questions.

## Corpus procédure civile (intégré le 07/11/2026 — `docs/INTEGRATION-procedure.md`)

Code de procédure civile 2011 (loi 2008-07) + loi modificative 2016-16 + projet 2020 (décret 2020-198, **non normatif**) : 1 303 enregistrements, recherche BM25+trigrammes (`src/search/procedure.py`), réponse déterministe citée (`POST /api/ask-procedure`). Règles : version 2016-16 servie à la place de l'original remplacé, projet 2020 uniquement en encadré « non confirmé comme adopté », citation = label + date + pages PDF + badge de statut + avertissement OCR. Tests d'acceptation T1–T7 : `python eval/test_procedure.py` → **7/7**.

**Lacunes connues (ne jamais les combler par invention) :**
- Loi 2016-16 : page imprimée 15 manquante dans le PDF fourni — articles **nouveaux 874, 883, 884, 886, 888, 894 absents** et fin du 881 ; obtenir une copie complète.
- Code de 2011 : **30 numéros non retrouvés** par l'OCR (liste dans `corpus/qa_report.md`, local) et 14 numéros réparés — ne jamais écrire « l'article X n'existe pas » à partir de ce corpus.
- Projet de 2020 : pas d'article 8, date d'adoption en blanc — retrouver la loi promulguée avant toute intégration comme droit en vigueur. Il cite une loi 2017-15 « procédure » alors que la 2017-15 connue concerne le foncier : chaîne de modifications à vérifier.
- 51 enregistrements `needs_review` (à relire avant démo, priorité aux délais). Écart relevé : l'item 17 du projet vise l'art. 589 dans son texte mais `proposed_target.articles` s'arrête à 588 (`approximate`) — la mention « projet 2020 » est donc dérivée du découpage par articles cités, sans réécrire le corpus.
- Droits : `rights_status` **à confirmer** → `corpus/articles.jsonl` et l'OCR procédure ne sont **pas versionnés** (voir `.gitignore`) ; seul `corpus/sources.json` (métadonnées) est publié. Ce corpus ne contient pas le code foncier : pour titre/héritage/expropriation, réponse « texte de base pas encore intégré » (`coverage_check`, R5).

## Licence & droits

Chaque source listée dans `corpus/manifest.json` avec son statut. Ne pas collecter `textes.justice.bj` (accès automatisé refusé) ni LEGIS sans autorisation.

## Historique des commits

Commits incrémentaux — les juges examinent l'historique.
