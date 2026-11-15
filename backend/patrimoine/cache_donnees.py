"""
Cache des tableaux de bord.

Le tableau de bord agrège tout le patrimoine d'une organisation : c'est la page la plus coûteuse,
et la plus souvent ouverte. Son résultat est gardé en cache quelques minutes.

Pour ne jamais afficher de chiffres périmés, chaque écriture sur une donnée agrégée
(bien, transaction, projet, alerte, mouvement, district, déclaration, document) incrémente un numéro de version.
Ce numéro fait partie de la clé du cache : une modification rend aussitôt l'ancienne entrée inutilisable.
Les mises à jour en masse (bulk_update), qui ne déclenchent pas de signal, appellent
explicitement donnees_modifiees().
"""
import time

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save

CLE_VERSION = "umurage:donnees:version"
DUREE = 300  # secondes


def version():
    v = cache.get(CLE_VERSION)
    if v is None:
        # Valeur de départ toujours croissante, même si le cache a été vidé : une ancienne clé ne peut pas revenir
        v = time.time_ns()
        cache.add(CLE_VERSION, v, timeout=None)
        v = cache.get(CLE_VERSION, v)
    return v


def donnees_modifiees(*args, **kwargs):
    try:
        cache.incr(CLE_VERSION)
    except ValueError:
        cache.set(CLE_VERSION, time.time_ns(), timeout=None)


def cle(*parties):
    return "umurage:" + ":".join(str(p) for p in parties) + f":v{version()}"


def brancher_signaux():
    from core.models import District, Organisation
    from finances.models import Transaction
    from iot.models import Alerte

    from .models import Bien, Declaration, Document, Mouvement, Projet

    for modele in (Bien, Transaction, Projet, Alerte, Mouvement, District, Declaration, Document, Organisation):
        post_save.connect(donnees_modifiees, sender=modele, dispatch_uid=f"cache-{modele.__name__}-save")
        post_delete.connect(donnees_modifiees, sender=modele, dispatch_uid=f"cache-{modele.__name__}-delete")


def en_cache(prefixe, *parties, calcul):
    """Renvoie le résultat de calcul() pour cette clé, en le calculant seulement si la version des données a changé."""
    c = cle(prefixe, *parties)
    donnees = cache.get(c)
    if donnees is None:
        donnees = calcul()
        cache.set(c, donnees, DUREE)
    return donnees
