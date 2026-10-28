# CONTEXTE — JuriAgent (reprise rapide en nouvelle conversation)

> Charger ce fichier en premier. Il évite de relire tout l'historique (Muse, legal-agent-workshop, hackathon, fiche de route).

## 1. Projet en 1 phrase
Assistant **anonyme**, **sourcé uniquement sur les textes officiels béninois**, qui aide un citoyen sans connaissances juridiques à comprendre sa situation foncière (héritage, titre, expropriation, expulsion, partage) et à préparer son RDV avocat/ANDF/mairie/tribunal.

## 2. Où on en est (28 oct 2026)
- **Dépôt** : `D:\hackathon\juriagent` → `https://github.com/bolouvipf/juriagent` (vide au départ, maintenant 1 commit `d96bbcf`)
- **Commit 1 fait** : `README.md`, `.gitignore`, `requirements.txt`, `.env.example`, `corpus/manifest.json`, `docs/Fiche-de-route-Muse.pdf`, arborescence `corpus/{raw,consolidated}`, `data/{ingested,index}`, `src/{ingest,search,agent,verifier,api}`, `web/`, `eval/`
- **Dépôt workshop** séparé : `D:\hackathon\legal-agent-workshop` + `D:\legal-agent-workshop\agent` (conservé pour référence, avec `helper.ps1` Windows, `.venv` Python 3.14, openai 2.54)
- **Commits incrémentaux obligatoires** : les juges examinent l'historique → ne jamais squash.

## 3. Contraintes hackathon (Meta Global AI Developer Hackathon 2026)
- **Période** : 26 oct → 4 nov 21h ET (05 nov 02:00 Paris). Objectif interne : soumettre 3 nov au soir.
- **Dépôt GitHub public**, travail nouveau clairement identifié.
- **Modèles Meta obligatoires** (usage réel, central, visible) : Muse Spark / Wonder / Muse Image / SAM 3.1 via API + open-weights via Baseten/Modal/Fireworks.
- **Tracks** : indie (créativité + ambition tech + ça marche) vs startup (exécution prod). Ici **indie tech**.
- **Thèmes** : *Build for Your World* ou *Push the Frontier* — le juridique est valide comme "ton monde", pas imposé.
- **Projets déconseillés** : chatbot simple, RAG basique, conseil juridique rendu par l'IA → d'où §5 ci-dessous.
- **Droits** : toute ressource sans droits = disqualification. Voir `corpus/manifest.json`.
- **Critères visés** : impact 30%, utilisation Meta 25%, démo 25%, profondeur tech 20%.

## 4. Principes non négociables (Fiche §5)
1. Explique, ne juge pas (pas de verdict, pas de stratégie)
2. Chaque affirmation sourcée (texte, article, date, lien) — pas de source = pas d'affirmation
3. Sait s'abstenir
4. Tient compte des dates (ex: art. 522-5 = 2 ans dès 2017 → potentiellement périmé)
5. Oriente vers humain (avocat, ANDF, mairie, tribunal)
6. Anonymat (pas de compte, pas de stockage par défaut)

## 5. Comportement attendu (§6, format fixe)
1. Comprendre : 3-5 questions courtes (type, commune, docs, dates, adversaire)
2. Rechercher : corpus avec filtre date/vigueur
3. Répondre : loi citée → mots simples → démarches → pièces → délais/validité → à qui s'adresser → ce que l'agent ne peut pas dire
4. Vérifier : 2e passe, supprime ce qui n'est pas appuyé
5. Préparer : export dossier (faits, pièces, questions pour RDV)

## 6. Corpus & droits (§7 — `corpus/manifest.json`)
| Source | Statut |
|---|---|
| Loi 2013-01 du 14/08/2013 (base) | À récupérer source officielle, conditions à vérifier |
| Loi 2017-15 du 10/08/2017 (modificative) | sgg.gouv.bj — mentions légales à lire |
| Décrets 2015 (007, 010 ANDF, 014, 018 PFR, 015/029 à identifier) | sgg.gouv.bj |
| LEGIS (legis.cdij.bj) | Reproduction interdite — autorisation demandée 28/10 en attente → NE PAS collecter |
| textes.justice.bj | Accès automatisé refusé → NE PAS collecter |
**Règle d'or** : 2017 est modificative (articles changés seuls) → travailler sur **consolidé 2013+2017**, jamais 2017 seule. Vérifier s'il existe des modifs post-2017 avant de figer.

## 7. Architecture (§8)
- **Ingestion** : découpage par article, métadonnées {texte, article, date_adoption, modifié_par, lien}
- **Recherche** : BM25 + sémantique, filtre date/vigueur
- **Rédaction** : Muse Spark (seuls passages retrouvés)
- **Vérificateur** : 2e appel, contrôle chaque affirmation vs passages
- **Interface** : page web FR, mobile, sans compte
- **Voix** : option si temps (transcription Meta FR)
- **Langues locales** : hors périmètre (mentionner en piste future)

## 8. Plan 7 jours (§9) — état
- J1-J2 : corpus + OCR Muse (144p) + ingestion + **consolidation 2013+2017 = 544 articles** → **fait (commits d96bbcf..80bf77b)**
- J3 : agent questions + réponse format fixe
- J4 : vérificateur + dates + test 20 questions
- J5 : interface + export + voix
- J6 : scénario démo (héritage/expropriation + cas de refus) + vidéo 3min + README
- J7 : marge + soumission

## 9. Stack & Modèles
- **Python 3.14** (déjà installé), FastAPI + Uvicorn, pypdf, rank-bm25, sentence-transformers, openai SDK
- **Meta API** : `https://api.meta.ai/v1`, modèles `muse-spark-1.3` (rédac), `muse-wonder-1.0` (verif) — config déjà dans `C:\Users\Kimsh\.config\opencode\opencode.jsonc:32` (clé `LLM_16157...`) + clé agent workshop `LLM_205342...` dans `D:\legal-agent-workshop\agent\.env` (ne pas committer)
- `.env.example` présent, `.env` ignoré
- **Opencode agents proposés** (non encore créés, voir `C:\Users\Kimsh\.config\opencode\agents\`) : `muse-architect`, `muse-builder`, `muse-verifier`, `muse-vision` (tous `meta/muse-*`)

## 10. Historique technique important
- Muse Code installé en `D:\muse` puis **supprimé** à ta demande + comptes sandbox `muse-sbx-r1/u1` + `C:\ProgramData\muse` + entrées PATH/config — nettoyés le 28/10 (log `muse-uninstall.log`)
- WSL Ubuntu avec `python3.14-venv` installé, `legal-agent-workshop` passé en CRLF→LF, helper Windows `helper.ps1` créé (portage natif, plus besoin de WSL)
- **Choix validé** : tu as dit d'utiliser mon plan et de ne pas attendre vérification des lois ("c'est publique"), commits incrémentaux

## 11. Prochaines etapes (reprise)
1. Tourner la video 3 min (docs/DEMO.md), serveur: python src/api/main.py
2. Optionnel: corriger les sur-abstentions H2/P3, voix (transcription Meta)
3. Soumission Cerebral Valley avant le 3 nov au soir (repo deja public et pousse)

## 12. Resultats mesures (eval/run_eval.py, 28 oct 2026)
- 20 questions: abstention conforme 18/20, citations valides 14/14, verdicts interdits 0, latence ~21 s
- Corpus: 544 articles loi consolidee + 192 articles decrets = 736 entrees
- Pipeline: OCR Muse Spark vision -> consolidation -> recherche hybride BM25+MiniLM -> redaction Spark -> verification Wonder + filtres deterministes
## 12. Commandes utiles
```bash
# env
python -m venv .venv && .\.venv\Scripts\activate
pip install -r requirements.txt
# ingest
python src/ingest/ingest.py --source corpus/raw --out data/ingested/articles.jsonl
# api
python src/api/main.py
# opencode (dans D:\hackathon\juriagent)
opencode
```

## 13. Fichiers clés à lire à la reprise
- `docs/Fiche-de-route-Muse.pdf` (5 pages — source de vérité)
- `corpus/manifest.json`
- `README.md`
- Ce `CONTEXTE.md`

---
*MAJ : 2026-10-28 — Commit 1 `d96bbcf`. Auteur: HOUETOR <bopiflo05@gmail.com>. À committer dès que ce fichier est validé.*
