# Performance : index et cache (priorité 1)

## Ce qui a changé

| Fichier | Changement |
|---|---|
| `patrimoine/views.py` | Tableau de bord recalculé par **agrégations SQL** (au lieu d'une boucle Python sur chaque bien) ; objectif santé 2030 en une requête au lieu de deux par district ; tableau de bord, carte et portail public **mis en cache** |
| `patrimoine/outils.py` | Page Qualité mise en cache (clé incluant la date du jour) |
| `patrimoine/cache_donnees.py` | Nouveau : cache versionné. Toute écriture sur un bien, une transaction, un projet, une alerte, un mouvement, un district, une déclaration, un document ou une organisation incrémente la version et invalide aussitôt les entrées |
| `ia/predictions.py`, `ia/anomalies.py` | Invalidation explicite après les `bulk_update` (qui ne déclenchent pas de signal) |
| `*/models.py` + 3 migrations | 9 index composés : `Bien(district, categorie)`, `Bien(district, etat)`, `Bien(score_risque)`, `Transaction(district, date)`, `Transaction(district, sens)`, `Transaction(est_anomalie, verifiee)`, `Mouvement(bien, -date)`, `Declaration(organisation, statut, -recue_le)`, `Alerte(bien, resolue)` |
| `core/tests.py` | 4 tests : invalidation immédiate, invalidation après mise à jour en masse, cloisonnement du cache par district et par organisation, portail public |

Les réponses de l'API sont **identiques** avant et après (comparaison automatique sur 11 réponses :
tableau de bord, carte, qualité pour l'évêque, un surintendant et l'organisation Rwanda, portail public).
Seule correction : à score de risque égal, les « biens à risque » sont désormais triés par identifiant (ordre stable).

## Mesures

Données de démonstration multipliées : **4 753 biens, 49 877 transactions, 9 583 mouvements** (SQLite, temps médian sur 5 appels).

| Page | Avant | Après, sans cache | Après, cache chaud | Requêtes SQL |
|---|---|---|---|---|
| Tableau de bord | 576 ms | 199 ms (×2,9) | **0,9 ms** | 42 → 16 |
| Portail public | 134 ms | 33 ms (×4) | **1,5 ms** | 9 → 10 |
| Qualité des données | 184 ms | 184 ms | **0,7 ms** | 3 → 3 |
| Carte | 195 ms | 204 ms | **26 ms** (×7) | 2 → 2 |
| Inventaire, recherche, finances | inchangés (6 à 38 ms) | | | |

Le cache dure 5 minutes au maximum, mais il est invalidé dès qu'une donnée change : il n'affiche jamais de chiffre périmé.

## Mise en production

```bash
cd backend
python manage.py migrate      # crée les 9 index
python manage.py test         # 26 tests
```

Le cache utilise le backend déjà configuré (fichiers). Avec plusieurs serveurs ou beaucoup d'utilisateurs,
passer à Redis dans `config/settings.py` (`django.core.cache.backends.redis.RedisCache`) : aucun autre changement n'est nécessaire.
