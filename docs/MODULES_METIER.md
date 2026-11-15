# Modules métier

Ces modules transforment UMURAGE d'un inventaire en un outil de gestion quotidienne. Ils sont regroupés dans
l'application Django `backend/metier` et dans le menu **Opérations**, **Patrimoine** et **Finances** de l'interface.

| # | Module | Écran | Qui agit |
|---|---|---|---|
| 1 | Circuits d'approbation | Opérations › Approbations | Tout membre demande ; surintendant, trésorier, évêque valident |
| 2 | Échéancier et rappels | Opérations › Échéancier | Direction, trésorerie, surintendants |
| 3 | Baux et loyers | Finances › Locations et loyers | Trésorerie, surintendants |
| 4 | Maintenance | Opérations › Maintenance | Surintendants, agents, trésorerie |
| 5 | Comptabilité du patrimoine | Finances › Comptabilité | Trésorerie, direction |
| 6 | Inventaire physique | Patrimoine › Inventaire physique | Surintendants, agents |
| 7 | Documents obligatoires | Échéancier › Documents obligatoires | Tous (lecture) |
| 8 | Sécurité du compte (double authentification) | Gouvernance › Sécurité du compte | Chaque utilisateur |
| 9 | Comparaison des églises | Pilotage › Comparaison des églises | Tous (dans leur périmètre) |

## 1. Circuits d'approbation

Une décision qui engage le patrimoine devient une **demande** qui suit un circuit :

| Type | Circuit |
|---|---|
| Cession, acquisition, transfert | Surintendant du district → Évêque |
| Travaux, dépense < seuil | Surintendant → Trésorier |
| Travaux, dépense ≥ seuil | Surintendant → Trésorier → Évêque |

Le seuil vaut 5 000 000 (monnaie locale) ; il se règle avec la variable `SEUIL_APPROBATION_DIRECTION`.

Règles : personne ne valide sa propre demande ; une même personne ne donne qu'un avis ; un rejet doit être motivé ;
chaque niveau est prévenu par WhatsApp. Une demande approuvée est ensuite **exécutée** :

- **cession** : mouvement « Cession » dans l'historique, le bien sort de l'inventaire actif (il reste consultable), la recette est enregistrée ;
- **transfert** : le bien change de district ;
- **travaux** : un ordre de travail est créé ;
- **dépense** : la transaction est enregistrée (par la trésorerie uniquement).

## 2. Échéancier

Assurances, impôts fonciers, titres, contrôles techniques, fins de bail, documents qui expirent. Les rappels partent
**30 jours avant, 7 jours avant, puis en cas de retard**, une seule fois chacun, au responsable désigné, sinon au
surintendant du district, sinon à la direction. Une échéance périodique (par exemple chaque année) se recrée dès
qu'elle est marquée « faite ». Les fins de bail et les documents datés créent leurs échéances automatiquement.

## 3. Baux et loyers

Un bail crée chaque mois une ligne de loyer. Encaisser un loyer enregistre une recette « Loyers perçus » rattachée au
bien (avec canal et référence Mobile Money). Les impayés apparaissent dès que l'échéance du mois est dépassée.

## 4. Maintenance

- **Ordres de travail** : demandé → planifié → en cours → terminé, avec fournisseur, devis et coût réel. Terminer un
  ordre l'inscrit dans l'historique du bien ; la trésorerie peut en enregistrer la dépense en même temps.
- **Entretien préventif** : un plan (par exemple « pompe du forage tous les 6 mois ») crée l'ordre de travail 15 jours avant.
- **Risque IA** : tout bien dont le score de risque atteint 70 reçoit une inspection prioritaire (urgente au-delà de 85).

## 5. Comptabilité du patrimoine

- **Budget et réalisé** : lignes votées par catégorie, comparées aux transactions ; dépassements, mouvements hors budget,
  dépenses de plus de 500 000 sans pièce justificative.
- **Registre des immobilisations** : amortissement linéaire au prorata des mois ; terrains non amortis ; export Excel (CSV).
  Durées par défaut (bâtiment 40 ans, infrastructure 25, équipement 5, véhicule 5, agricole 10) **à valider par l'expert-comptable**.
- **Rapprochement** : import d'un relevé bancaire ou Mobile Money en CSV (date, montant, référence).
- **Clôture d'exercice** : après clôture, aucune transaction de l'année ne peut être créée, modifiée ou supprimée.

## 6. Inventaire physique

Une campagne (district ou organisation entière) ; l'agent scanne le QR code ou tape le code de chaque bien, indique
l'état constaté ou « introuvable ». La clôture fige le procès-verbal, peut appliquer les états constatés à l'inventaire,
et ouvre une inspection pour chaque bien introuvable.

## 7. Documents obligatoires

Terrain titré → titre foncier ; véhicule → carte grise et assurance ; bâtiment de plus de 50 000 000 → assurance.
Un document peut porter une date d'expiration, une version, et être la pièce justificative d'une transaction.

## 8. Comparaison des églises

Les églises locales (paroisses) ou les districts de l'organisation, comparés sur les mêmes indicateurs : biens,
valeur, patrimoine par membre, complétude des fiches, terrains titrés, biens à risque, travaux en attente, loyers ;
pour les districts, recettes, dépenses, solde et dîmes par membre. L'**indice de bonne gestion** (sur 100) est la
moyenne de la complétude des fiches, de la part de terrains titrés, de la part de biens hors risque élevé et du taux
de recouvrement des loyers. Jusqu'à 4 entités peuvent être mises côte à côte. Un surintendant ne compare que les
églises de son district ; aucune donnée d'une autre organisation n'est jamais affichée.

## Voyants

Les pastilles de la barre latérale et de la cloche suivent la gravité : **rouge clignotant** = critique (échéance en
retard, travail urgent, alerte critique d'un capteur), **rouge** = loyers impayés depuis plus de 60 jours,
**orange** = à traiter, **bleu** = information. Le clignotement est désactivé si le système demande de réduire les animations.

## 7. Registre officiel des membres

Page **Vie de l'Église → Registre des membres** (`/registre`, API `/api/registre/`).

- Grande fiche d'adhésion en trois sections (identité avec photo, contact et famille, vie de l'Église), avec une illustration animée
  qui écrit dans le registre pendant la saisie, un anneau de progression et un aperçu en direct de la carte de membre.
- Numéro officiel attribué une seule fois : `DISTRICT-ANNÉE-NNNNN` (ex. `GIT-2026-00014`).
- Contrôles : nom et prénom mis en forme, date de naissance non future, baptême après la naissance,
  **doublon** signalé (même nom, prénom et date de naissance) avec confirmation explicite.
- Cloisonnement : un surintendant ou un agent n'enregistre et ne voit que les églises de son district.
- Une fiche ne se supprime pas (sauf administrateur) : on change son statut (transféré, décédé). Tout est tracé dans le journal d'audit.
- Carte de membre imprimable au format carte bancaire (85,6 × 54 mm).
- Statistiques : membres actifs, baptisés et confessants, nouveaux du mois, taux d'enregistrement par rapport à l'effectif déclaré de chaque église.

## 8. Statistiques de l'Église

Page **Vie de l'Église → Statistiques de l'Église** (`/statistiques`, API `/api/statistiques-eglise/?district=`).

- Bandeau « salle de contrôle » : membres actifs (avec courbe), baptisés, églises locales, taux d'enregistrement, valeur du patrimoine, dossiers en attente.
- Nouveaux membres par mois et recettes / dépenses sur 12 mois.
- **Année en cours comparée à l'année précédente, à la même date** (du 1er janvier au jour J de chaque année) :
  nouveaux membres, baptêmes, recettes, dîmes, dépenses, solde, biens acquis, travaux terminés, déclarations. Vert = amélioration, rouge = dégradation.
- **Districts côte à côte** : quatre petits graphiques triés (membres, patrimoine, recettes, dîmes par membre) ou un tableau avec le meilleur en vert et le plus faible en rouge.
- Membres par statut, pyramide des âges (femmes / hommes), ministères ; patrimoine par catégorie et état des biens.
- Couleurs fixes par entité, palette vérifiée pour le daltonisme ; chaque graphique a des étiquettes ou une légende chiffrée.
- Cartes financières colorées (recettes, dépenses, solde, dîmes, loyers) avec mini-courbe et évolution depuis janvier.
- Projection de fin d'année au rythme actuel (réalisé, projection, année précédente complète).
- Répartition des recettes et des dépenses par catégorie, avec barres de données.
- Tableau des églises locales à mise en forme conditionnelle (vert favorable, bleu indicatif, rouge à surveiller), triable.
- Tableau mensuel sur 12 mois avec barres de données et total.
