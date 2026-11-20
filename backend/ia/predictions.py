"""
Maintenance prédictive (score de risque des biens) et prévisions financières.
"""
from collections import defaultdict
from datetime import date

import numpy as np
from django.db.models import Max, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from finances.models import Transaction
from patrimoine.models import Bien, Mouvement
from patrimoine.cache_donnees import donnees_modifiees

ETAT_POIDS = {"BON": 0, "MOYEN": 25, "MAUVAIS": 50, "CONSTRUCTION": 5}
DUREE_DEFAUT = {"FON": None, "IMM": 50, "INF": 25, "EQP": 8, "VEH": 10, "AGR": 6}


_NON_FOURNI = object()


def score_risque(bien: Bien, derniere_maintenance=_NON_FOURNI, alertes_ouvertes=None):
    """Score de 0 (aucun risque) à 100 (intervention urgente), avec ses facteurs."""
    if bien.categorie == "FON":
        # Pour un terrain, le risque principal est juridique (spoliation, litige)
        facteurs = []
        score = 0
        if bien.statut_juridique == "SANS_TITRE":
            score += 70
            facteurs.append("Terrain sans titre de propriété")
        elif bien.statut_juridique == "EN_COURS":
            score += 35
            facteurs.append("Titre de propriété en cours d'obtention")
        return min(100, score), facteurs

    facteurs, score = [], 0
    if ETAT_POIDS.get(bien.etat):
        score += ETAT_POIDS[bien.etat]
        facteurs.append(f"État : {bien.get_etat_display().lower()}")
    duree = bien.duree_vie_ans or DUREE_DEFAUT.get(bien.categorie)
    if duree and bien.age_ans:
        usure = min(1.0, bien.age_ans / duree)
        if usure > 0.5:
            score += round(30 * usure)
            facteurs.append(f"Usure : {round(100 * usure)} % de la durée de vie")
    if derniere_maintenance is _NON_FOURNI:
        derniere_maintenance = (
            bien.mouvements.filter(type__in=["MAINTENANCE", "REPARATION", "INSPECTION"]).aggregate(d=Max("date"))["d"]
        )
    if bien.etat != "CONSTRUCTION":
        if derniere_maintenance:
            mois = (date.today() - derniere_maintenance).days / 30.4
            if mois > 12:
                score += min(25, round(mois))
                facteurs.append(f"Aucun entretien depuis {round(mois)} mois")
        else:
            score += 15
            facteurs.append("Aucun entretien enregistré")
    if alertes_ouvertes is None:
        alertes_ouvertes = bien.alertes.filter(resolue=False).count()
    if alertes_ouvertes:
        score += 20 * alertes_ouvertes
        facteurs.append(f"{alertes_ouvertes} alerte(s) capteur non résolue(s)")
    return min(100, score), facteurs


def recalculer_risques(biens=None):
    maint = dict(
        Mouvement.objects.filter(type__in=["MAINTENANCE", "REPARATION", "INSPECTION"])
        .values("bien")
        .annotate(d=Max("date"))
        .values_list("bien", "d")
    )
    biens = list((biens if biens is not None else Bien.objects.all()).prefetch_related("alertes"))
    for b in biens:
        ouvertes = sum(1 for a in b.alertes.all() if not a.resolue)
        b.score_risque, _ = score_risque(b, maint.get(b.pk), ouvertes)
    Bien.objects.bulk_update(biens, ["score_risque"])
    donnees_modifiees()  # bulk_update ne déclenche pas de signal : on invalide le cache des tableaux de bord
    return len(biens)


def ecarter_mois_incomplets(mois, volume, minimum=6):
    """Sépare les mois complets des derniers mois incomplets.

    Sont incomplets, en fin de série : le mois en cours, et les mois dont le volume (recettes + dépenses)
    est inférieur au quart de la médiane des douze mois précédents (saisie en retard). Les compter comme
    des mois entiers ferait chuter les courbes et fausserait la tendance. On garde au moins `minimum` mois.
    Renvoie (mois_complets, mois_ecartes), dans l'ordre chronologique.
    """
    mois = list(mois)
    aujourd_hui = timezone.localdate()
    exclus = []
    while len(mois) > minimum:
        m = mois[-1]
        reference = float(np.median([volume(x) for x in mois[-13:-1]]))
        en_cours = (m.year, m.month) == (aujourd_hui.year, aujourd_hui.month)
        if en_cours or (reference > 0 and volume(m) < 0.25 * reference):
            exclus.insert(0, mois.pop())
            continue
        break
    return mois, exclus


def prevision_financiere(qs, horizon=6):
    """
    Prévision mensuelle des recettes et dépenses : tendance linéaire + saisonnalité
    mensuelle, avec un intervalle de confiance à environ 80 %.
    """
    lignes = (
        qs.annotate(mois=TruncMonth("date")).values("mois", "sens").annotate(total=Sum("montant_bif")).order_by("mois")
    )
    series = defaultdict(dict)
    for l in lignes:
        m = l["mois"]
        m = m.date() if hasattr(m, "date") else m
        series[l["sens"]][m] = float(l["total"])
    resultat = {"historique": [], "prevision": []}
    if not series:
        return resultat

    tous_mois, exclus = ecarter_mois_incomplets(
        sorted({m for s in series.values() for m in s}),
        lambda m: series["RECETTE"].get(m, 0) + series["DEPENSE"].get(m, 0))
    resultat["mois_incomplets"] = [m.strftime("%Y-%m") for m in exclus]
    for m in tous_mois:
        resultat["historique"].append(
            {"mois": m.strftime("%Y-%m"), "recettes": series["RECETTE"].get(m, 0), "depenses": series["DEPENSE"].get(m, 0)}
        )
    if len(tous_mois) < 6:
        return resultat

    futurs = []
    a, mo = tous_mois[-1].year, tous_mois[-1].month
    for _ in range(horizon):
        mo += 1
        if mo > 12:
            a, mo = a + 1, 1
        futurs.append(date(a, mo, 1))

    def projeter(sens):
        y = np.array([series[sens].get(m, 0) for m in tous_mois])
        t = np.arange(len(y))
        pente, origine = np.polyfit(t, y, 1)
        residus = y - (pente * t + origine)
        saison = defaultdict(list)
        for m, r in zip(tous_mois, residus):
            saison[m.month].append(r)
        saison = {k: float(np.mean(v)) for k, v in saison.items()}
        ecart = float(np.std([r - saison[m.month] for m, r in zip(tous_mois, residus)]))
        sortie = []
        for i, m in enumerate(futurs):
            v = max(0.0, pente * (len(y) + i) + origine + saison.get(m.month, 0))
            sortie.append((v, max(0.0, v - 1.28 * ecart), v + 1.28 * ecart))
        return sortie

    rec, dep = projeter("RECETTE"), projeter("DEPENSE")
    for m, r, d in zip(futurs, rec, dep):
        resultat["prevision"].append({
            "mois": m.strftime("%Y-%m"),
            "recettes": round(r[0]), "recettes_bas": round(r[1]), "recettes_haut": round(r[2]),
            "depenses": round(d[0]), "depenses_bas": round(d[1]), "depenses_haut": round(d[2]),
        })
    return resultat
