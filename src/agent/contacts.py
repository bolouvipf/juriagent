#!/usr/bin/env python3
"""
Qui contacter (JuriAgent): interlocuteurs nommes par les textes eux-memes.
Aucune adresse ni telephone invente: role, quoi demander, base legale (article).
La commune saisie personnalise mairie et services locaux.
"""


def contacts_for(situation: dict) -> list[dict]:
    commune = (situation.get("commune") or "").strip()
    mairie = f"Mairie de {commune}" if commune else "Votre mairie"
    type_ = (situation.get("type") or "").lower()

    base = {
        "heritage": [
            {"qui": "Un notaire ou le juge", "role": "Faire etablir l'acte de notoriete ou l'intitule d'inventaire apres le deces",
             "demander": "Quels actes pour constater la transmission aux heritiers ?", "base": "Article 166"},
            {"qui": "Le regisseur de la propriete fonciere (conservation fonciere)", "role": "Inscrire la mutation par deces sur le titre foncier",
             "demander": "Quelles pieces pour inscrire la mutation apres deces ?", "base": "Articles 159 et 166"},
            {"qui": "Un avocat", "role": "Si les heritiers ne sont pas d'accord sur le partage",
             "demander": "Comment proteger mes droits dans la succession ?", "base": "Orientation (l'assistant ne juge pas)"},
        ],
        "titre": [
            {"qui": "Le regisseur de la propriete fonciere (conservation fonciere)", "role": "Confirmation de droits fonciers et delivrance du titre foncier",
             "demander": "Comment ouvrir ma procedure de confirmation de droits ?", "base": "Articles 112 a 116"},
            {"qui": "L'ANDF (Agence Nationale du Domaine et du Foncier)", "role": "Pilotage des procedures foncieres et registres",
             "demander": "Ou en est le registre foncier de ma commune ?", "base": "Articles 4 et 7 ; decret 2015-010"},
            {"qui": mairie, "role": "Plan foncier rural et demarches foncieres locales",
             "demander": "Mon terrain est-il inscrit au plan foncier rural ?", "base": "Articles 121 et 202"},
        ],
        "expropriation": [
            {"qui": "L'ANDF", "role": "Procedures touchant au domaine de l'Etat",
             "demander": "Quelle est la procedure d'expropriation et d'indemnisation prevue ?", "base": "Decret 2015-010"},
            {"qui": mairie, "role": "Information locale sur le projet et les parcelles concernees",
             "demander": "Le projet est-il officiel et ma parcelle est-elle concernee ?", "base": "Article 202"},
            {"qui": "Un avocat ou le tribunal competent", "role": "Contestation et indemnisation",
             "demander": "Comment contester ou faire evaluer mon indemnisation ?", "base": "Orientation (l'assistant ne juge pas)"},
        ],
        "expulsion": [
            {"qui": "Le tribunal competent", "role": "Seul un juge peut ordonner une expulsion ou trancher une occupation",
             "demander": "Comment saisir le tribunal pour faire constater mes droits ?", "base": "Articles 89 et suivants"},
            {"qui": mairie + " / Commission de Gestion Fonciere", "role": "Mediation locale, surtout en milieu rural",
             "demander": "Une mediation est-elle possible avant le tribunal ?", "base": "Articles 423 a 426"},
            {"qui": "Un avocat", "role": "Strategie et procedure contentieuse",
             "demander": "Quelles demarches engager dans mon cas ?", "base": "Orientation (l'assistant ne juge pas)"},
        ],
        "partage": [
            {"qui": "Un geometre agree", "role": "Bornage et plans des lots lors d'un partage ou morcellement",
             "demander": "Etablir les plans des lots a distraire", "base": "Article 183"},
            {"qui": "Le regisseur de la propriete fonciere", "role": "Depot des plans et inscription de l'acte de partage",
             "demander": "Quelles pieces deposer pour le partage ?", "base": "Article 183"},
            {"qui": "Un notaire", "role": "Acte de partage entre proprietaires ou heritiers",
             "demander": "Rediger l'acte de partage", "base": "Article 166 (par analogie succession)"},
        ],
    }
    default = [
        {"qui": "L'ANDF (Agence Nationale du Domaine et du Foncier)", "role": "Point d'entree des procedures foncieres",
         "demander": "Qui est competent pour ma situation ?", "base": "Decret 2015-010"},
        {"qui": mairie, "role": "Demarches foncieres locales et plan foncier rural",
         "demander": "Quels services fonciers existent dans la commune ?", "base": "Article 202"},
        {"qui": "Un avocat", "role": "Analyse de votre situation precise",
         "demander": "Quels sont mes droits et mes recours ?", "base": "Orientation (l'assistant ne juge pas)"},
    ]
    return base.get(type_, default)
