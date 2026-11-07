# JuriAgent – Intégration du corpus juridique (instructions pour l’agent de code)

## 0. Objectif

Intégrer `corpus/articles.jsonl` (1 303 enregistrements) et `corpus/sources.json` dans la recherche de JuriAgent, avec trois garanties : **statut respecté**, **version la plus récente servie**, **source citée avec page**. L’agent explique, il ne juge jamais.

Ne rien réécrire à la main dans le corpus. Si un texte est faux, on corrige le script `corpus/scripts/build_corpus.py` ou on signale dans `qa_report.md`.

## 1. Fichiers fournis

| Fichier | Rôle |
|---|---|
| `corpus/articles.jsonl` | Un enregistrement par article (ou par « point » d’une loi modificative) |
| `corpus/sources.json` | Registre des 3 documents : date, statut, droits, origine |
| `corpus/qa_report.md` | Lacunes connues et enregistrements à relire |
| `corpus/ocr/*.txt` | Texte OCR brut par page (marqueurs `=== PAGE n ===`) |
| `corpus/scripts/` | `ocr_run.sh` (OCR français) et `build_corpus.py` (découpage) |

## 2. Schéma d’un enregistrement

`id`, `doc_id`, `doc_title`, `doc_date`, `status`, `normative` (bool), `kind`, `article`, `label`, `heading_path`, `text`, `page_start`, `page_end`, `ocr_clean` (toujours `false`), `needs_review` (bool).

Champs conditionnels :
- `modifies` `{doc_id, article, effect:"replace"}` : sur les articles « nouveau » de la loi 2016-16.
- `superseded_by` (liste d’ids) : sur les articles du code de 2011 déjà remplacés (45 cas).
- `proposed_changes` (liste d’ids) : articles du code de 2011 que le **projet** de 2020 voudrait modifier.
- `proposed_target` `{doc_id, articles, approximate:true}` : cible visée par un point du projet de 2020.
- `number_repaired` : le numéro d’article a été corrigé par cohérence de séquence (14 cas).

Valeurs de `status` : `en_vigueur_texte_origine`, `promulguee`, `projet_non_adopte_dans_ce_document`.
Valeurs de `kind` : `base`, `modificative`, `projet_article`, `projet_item`, `decret_transmission`.

## 3. Règles que le code doit faire respecter

**R1 – Statut.** Seuls les enregistrements `normative: true` peuvent être présentés comme « ce que dit la loi ». Les `kind` `projet_*` et `decret_transmission` ne s’affichent que dans un encadré séparé : « Projet de loi (2020) : non confirmé comme adopté ». Jamais comme règle en vigueur.

**R2 – Résolution de version.** Si un enregistrement a `superseded_by` non vide, ne pas le renvoyer : renvoyer l’enregistrement qui le remplace et afficher « version loi 2016-16 ». Si un article renvoyé a `proposed_changes`, ajouter la ligne : « Un projet de 2020 propose de le modifier ; vérifier s’il a été adopté ».

**R3 – Citation obligatoire.** Chaque affirmation de la réponse référence un `id`. Affichage : `label` + titre court du texte + `doc_date` + « p. `page_start`–`page_end` du PDF » + badge de statut. Ajouter : « Texte issu d’une reconnaissance automatique : vérifier sur le document officiel ».

**R4 – Abstention.** Pas d’`id` pertinent trouvé, ou enregistrement `needs_review` dont le sens dépend d’un chiffre ou d’un délai : l’agent le dit et oriente vers un professionnel. Il ne comble jamais avec ses connaissances générales. Aucune prédiction d’issue, aucun verdict de culpabilité.

**R5 – Couverture.** Le corpus ne contient **pas encore** : le code foncier et domanial (loi 2013-01), la loi 2017-15 et les décrets d’application. Pour une question sur titre foncier, héritage, expropriation ou propriété, répondre « texte de base pas encore intégré » et ne rien déduire du code de procédure. Implémenter `coverage_check(question) -> doc_ids requis manquants`.

**R6 – Droits.** Ne pas committer `corpus/ocr/` ni `articles.jsonl` dans le dépôt public tant que `rights_status` n’est pas confirmé. Ajouter `corpus/` au `.gitignore`, charger le corpus depuis un stockage privé ou une variable d’environnement, et ne publier que `sources.json` (métadonnées). Ne pas collecter automatiquement textes.justice.bj (accès automatisé refusé).

## 4. Indexation (ordre recommandé)

1. **Chargeur** : lire le JSONL et `sources.json`, valider le schéma, refuser un enregistrement sans `status`.
2. **Recherche lexicale d’abord** (BM25 sur ~1 300 enregistrements suffit). Texte indexé = `heading_path` + `label` + `text`. Normaliser : minuscules, sans accents, sans ponctuation. **Ne pas corriger l’OCR dans le texte stocké.** Ajouter une correspondance floue par trigrammes pour absorber les erreurs (« Aticle », « oppel »). Embeddings : seulement s’ils sont autorisés par les règles du hackathon, sinon s’en passer.
3. **Résolveur de version** (R2) appliqué après la recherche.
4. **Découpage des gros enregistrements** : `decret-2020-198#proj-art3-item17` (~9 900 car.) et `#proj-art3-item21` contiennent plusieurs articles cités ; les couper à chaque « Article N : » en gardant l’id parent. `loi-2016-16#art-776-nouveau` (776.1 à 776.9) peut rester entier.
5. **Interface** : badge de statut, bloc « Projet non confirmé » distinct, et bouton « Voir la source » (doc, pages).
6. **Vérificateur** : seconde passe qui contrôle que chaque phrase de la réponse s’appuie sur un `id` cité ; supprimer ou signaler le reste.

## 5. Lacunes connues (à afficher dans le README du dépôt)

- **Loi 2016-16 : page manquante.** Le PDF fourni n’a que 16 pages et saute la page imprimée « 15 ». Articles absents : **883, 884, 886, 888, 894** et la fin du 881. Obtenir une copie complète ; en attendant, ne pas affirmer le contenu de ces articles.
- **Code de 2011 : 30 numéros non retrouvés** par la reconnaissance (liste dans `qa_report.md`) et **14 numéros réparés** (`number_repaired`). Ne jamais écrire « l’article X n’existe pas » à partir de ce corpus.
- **Projet de 2020 : pas d’article 8** dans la séquence, et date d’adoption laissée en blanc. Retrouver la loi promulguée avant de l’intégrer comme droit.
- Le projet de 2020 cite la loi 2017-15 comme ayant modifié le code de procédure ; la loi 2017-15 déjà lue concerne le code foncier. À vérifier avant d’établir la chaîne de modifications.
- 51 enregistrements ont `needs_review: true` (texte très court, caractères suspects ou numéro réparé). Les relire avant la démo, en priorité ceux liés à des délais.

## 6. Tests d’acceptation (vérifient les `id`, pas le contenu juridique)

| # | Question | Résultat attendu |
|---|---|---|
| T1 | « Quel est le délai d’appel en matière contentieuse ? » | Renvoie `loi-2016-16#art-621-nouveau`, pas `loi-2008-07#art-621` |
| T2 | « Comment faire appel d’une décision en matière foncière ? » | Le projet 2020 (art. 4) n’apparaît que dans l’encadré « projet », jamais comme règle |
| T3 | « Délai d’appel contre le juge de l’exécution » | `loi-2016-16#art-589-nouveau` + mention de `proposed_changes` |
| T4 | « Que dit l’article 884 ? » | Aveu de lacune (page manquante), aucune invention |
| T5 | « Vais-je gagner mon procès ? » | Refus de prédire + orientation vers un professionnel |
| T6 | « Mon voisin a pris une partie de mon terrain, quel est mon titre ? » | `coverage_check` : texte foncier de base non intégré |
| T7 | Toute réponse | Contient `label`, date, pages, badge de statut |

## 7. Mise à jour du corpus

Pour ajouter un texte : déposer le PDF, lancer `scripts/ocr_run.sh` (adapter la liste de documents), ajouter l’entrée dans `DOCS` de `build_corpus.py`, relancer, lire `qa_report.md`. Renseigner `source_origin` et `rights_status` dans `sources.json` avant toute publication.
