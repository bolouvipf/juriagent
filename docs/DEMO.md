# Script de démonstration — vidéo 3 minutes

Démarrer avant tournage : `python src/api/main.py` puis ouvrir http://localhost:8000 (vue téléphone du navigateur).

## 0:00–0:30 — Le problème
« Au Bénin, les litiges fonciers sont parmi les plus fréquents. Les textes officiels existent, en français, mais dispersés et difficiles à lire — surtout quand les PDF officiels sont de simples scans. JuriAgent aide un citoyen, anonymement, à comprendre sa situation et à préparer son rendez-vous. »

## 0:30–1:00 — Le corpus (profondeur technique)
Montrer le terminal : PDF scanné 2013-01 (0 texte extractible) → OCR par **Muse Spark vision** (144 pages) → consolidation 2013+2017 (544 articles, les articles supprimés retirés) → 6 décrets 2015 (192 articles). « 736 textes interrogeables, chacun avec sa source officielle. »

## 1:00–2:00 — Cas 1 : partage après héritage (ça marche)
Question : « Mon père est décédé, nous sommes 4 enfants, comment partager son terrain à Abomey-Calavi ? »
Montrer : citations [Article 10], [Article 183] cliquables vers sgg.gouv.bj → « En mots simples » → démarches → pièces → bouton **Exporter mon dossier**.

## 2:00–2:30 — Cas 2 : le refus (les principes)
Question : « Vais-je gagner mon procès contre mon frère ? »
Montrer l'abstention + orientation ANDF/avocat. « Il explique, il ne juge pas. Chaque affirmation est vérifiée par un second modèle, Muse Spark (verificateur) : ce qui n'est pas dans les textes est supprimé. »

## 2:30–3:00 — Les mesures (honnêteté)
Montrer `eval/resultats.json` : 20 questions fixées, **18/20 abstentions conformes, 14/14 citations valides, 0 verdict interdit**, ~21 s/question. « Limites : corpus = code foncier + décrets 2015. Pistes : langues locales, relecture par des juristes. »
