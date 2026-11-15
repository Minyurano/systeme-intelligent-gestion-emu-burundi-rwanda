# Reprise des données réelles

Les montants, surfaces, transactions, ventes de référence et mesures de capteurs fournis sont **fictifs**. Tant que
le vrai patrimoine n'est pas saisi, UMURAGE reste une démonstration. Démarche conseillée : un district pilote, un mois.

## Avant de commencer

1. Choisir le district pilote (par exemple Gitega) et nommer un référent données.
2. Créer l'organisation réelle (`/inscription`) ou repartir d'une base vide (sans `seed_demo`).
3. Créer les comptes : surintendant, agents de collecte, trésorier ; activer la double authentification des rôles sensibles.

## Ordre de saisie

| Étape | Données | Outil |
|---|---|---|
| 1 | Districts, paroisses | Paramètres |
| 2 | Biens (terrains, bâtiments, forages, véhicules, équipements) | Inventaire › Importer (modèle Excel fourni) |
| 3 | Titres fonciers, cartes grises, assurances (avec dates d'expiration) | Fiche du bien › Documents |
| 4 | Baux en cours | Locations et loyers |
| 5 | Échéances connues (assurances, impôts) | Échéancier |
| 6 | Fournisseurs et plans d'entretien des forages | Maintenance |
| 7 | Budget de l'année | Comptabilité |
| 8 | Transactions depuis le 1er janvier | Finances › Import ou saisie |
| 9 | Première campagne d'inventaire physique : elle vérifie tout ce qui précède | Inventaire physique |

## Contrôles de fin de reprise

- Qualité des données ≥ 75 % pour le district pilote (Pilotage › Qualité des données) ;
- aucune pièce obligatoire manquante pour les terrains titrés et les véhicules ;
- inventaire physique clôturé, écarts traités ;
- relevé bancaire du mois rapproché.

## Indicateurs à mesurer pendant le pilote

Temps moyen de recensement d'un bien, nombre de biens sans titre identifiés, loyers impayés recouvrés,
échéances tenues à temps, délai moyen de décision des demandes. Ces chiffres font l'étude de cas présentée aux autres
districts et aux partenaires.
