"""
Valorisation automatique du patrimoine.

- Terrains et bâtiments : modèle d'apprentissage (Random Forest) entraîné sur des
  ventes comparables du marché local, avec une explication de chaque estimation.
- Équipements, véhicules, infrastructures, agricole : amortissement linéaire.
"""
import math
from decimal import Decimal
from pathlib import Path

import joblib
import numpy as np
from django.conf import settings
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import cross_val_score

from core.models import District
from patrimoine.models import Bien

from .models import ComparableMarche, EntrainementModele

DOSSIER_MODELES = Path(settings.BASE_DIR) / "ia_modeles"


def _chemin(organisation_id):
    # Un modèle par organisation : chaque marché foncier (et chaque monnaie) est différent
    return DOSSIER_MODELES / f"valorisation_{organisation_id}.joblib"
ETAT_CODE = {"BON": 0, "MOYEN": 1, "MAUVAIS": 2, "CONSTRUCTION": 1}
DUREE_VIE_DEFAUT = {"EQP": 8, "VEH": 10, "INF": 25, "AGR": 6}
RESIDUEL = 0.10  # un bien amorti garde 10 % de sa valeur
LIBELLES = {
    "log_surface": "Surface",
    "age": "Âge du bien",
    "etat": "État",
    "distance": "Distance au chef-lieu",
    "categorie": "Type (terrain / bâtiment)",
}


def distance_km(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return 5.0
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class _Encodeur:
    """Transforme un bien ou un comparable en vecteur de caractéristiques."""

    def __init__(self, districts):
        self.districts = list(districts)  # codes, dans un ordre fixe
        self.noms = list(LIBELLES) + [f"district_{c}" for c in self.districts]

    def vecteur(self, categorie, surface, age, etat, distance, district_code):
        v = [
            math.log1p(surface or 0),
            age or 0,
            ETAT_CODE.get(etat, 0),
            distance,
            1 if categorie == "IMM" else 0,
        ]
        v += [1 if district_code == c else 0 for c in self.districts]
        return v


def entrainer(organisation_id):
    comps = list(ComparableMarche.objects.filter(district__organisation_id=organisation_id).select_related("district"))
    if len(comps) < 20:
        raise ValueError("Il faut au moins 20 ventes comparables pour entraîner le modèle de cette organisation.")
    enc = _Encodeur(District.objects.filter(organisation_id=organisation_id).order_by("code").values_list("code", flat=True))
    X = np.array(
        [enc.vecteur(c.categorie, c.surface_m2, c.age_ans, c.etat, c.distance_ville_km, c.district.code) for c in comps]
    )
    y = np.log(np.array([float(c.prix_bif) for c in comps]))
    modele = RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=42)
    r2 = cross_val_score(modele, X, y, cv=5, scoring="r2").mean()
    modele.fit(X, y)
    DOSSIER_MODELES.mkdir(exist_ok=True)
    joblib.dump({"modele": modele, "encodeur": enc, "reference": np.median(X, axis=0)}, _chemin(organisation_id))
    metriques = {"r2_validation_croisee": round(float(r2), 3), "organisation": organisation_id}
    EntrainementModele.objects.create(modele="valorisation", nb_exemples=len(comps), metriques=metriques)
    return metriques


_cache = {}


def _charger(organisation_id):
    chemin = _chemin(organisation_id)
    if not chemin.exists():
        entrainer(organisation_id)
    cle = (organisation_id, chemin.stat().st_mtime)
    if _cache.get(organisation_id, (None,))[0] != cle:
        _cache[organisation_id] = (cle, joblib.load(chemin))
    return _cache[organisation_id][1]


def _estimer_ml(bien: Bien):
    paquet = _charger(bien.district.organisation_id)
    modele, enc, ref = paquet["modele"], paquet["encodeur"], paquet["reference"]
    d = bien.district
    dist = distance_km(bien.latitude, bien.longitude, d.latitude, d.longitude)
    age = 0 if bien.categorie == "FON" else bien.age_ans  # un terrain ne s'use pas
    x = np.array(enc.vecteur(bien.categorie, bien.surface_m2, age, bien.etat, dist, d.code))
    pred_log = modele.predict([x])[0]
    valeur = math.exp(pred_log)
    # Intervalle : dispersion des prédictions des arbres de la forêt
    arbres = np.exp([t.predict([x])[0] for t in modele.estimators_])
    bas, haut = np.percentile(arbres, [10, 90])

    # Explication par occlusion : on remplace chaque caractéristique par sa valeur
    # médiane et on mesure de combien l'estimation change.
    facteurs = []
    for i, nom in enumerate(LIBELLES):
        x2 = x.copy()
        x2[i] = ref[i]
        effet = valeur - math.exp(modele.predict([x2])[0])
        facteurs.append({"facteur": LIBELLES[nom], "effet_bif": round(effet), "effet_pct": round(100 * effet / valeur, 1)})
    x2 = x.copy()
    nb = len(LIBELLES)
    x2[nb:] = ref[nb:]
    effet = valeur - math.exp(modele.predict([x2])[0])
    facteurs.append({"facteur": f"Localisation ({d.nom})", "effet_bif": round(effet), "effet_pct": round(100 * effet / valeur, 1)})
    facteurs = [f for f in facteurs if abs(f["effet_bif"]) >= 1000]
    facteurs.sort(key=lambda f: -abs(f["effet_bif"]))

    return {
        "valeur": round(valeur, -3),
        "intervalle": [round(bas, -3), round(haut, -3)],
        "methode": "Modèle ML (comparables du marché)",
        "facteurs": facteurs,
        "details": {"distance_chef_lieu_km": round(dist, 1)},
    }


def _estimer_amortissement(bien: Bien):
    acq = float(bien.valeur_acquisition or 0)
    duree = bien.duree_vie_ans or DUREE_VIE_DEFAUT.get(bien.categorie, 10)
    age = bien.age_ans or 0
    ratio = max(RESIDUEL, 1 - age / duree)
    if bien.etat == "MAUVAIS":
        ratio *= 0.7
    valeur = acq * ratio
    return {
        "valeur": round(valeur, -3),
        "intervalle": [round(valeur * 0.85, -3), round(valeur * 1.1, -3)],
        "methode": "Amortissement linéaire",
        "facteurs": [
            {"facteur": "Valeur d'acquisition", "effet_bif": round(acq), "effet_pct": 100.0},
            {"facteur": f"Usure : {age} ans sur {duree} ans de durée de vie", "effet_bif": round(valeur - acq),
             "effet_pct": round(100 * (valeur - acq) / acq, 1) if acq else 0},
        ],
        "details": {"duree_vie_ans": duree, "taux_residuel": RESIDUEL},
    }


def _estimer_construction(bien: Bien):
    """Un bâtiment en chantier vaut ce qui y a été investi, pas encore sa valeur de marché."""
    from patrimoine.models import Projet

    engage = sum(float(p.depense) for p in Projet.objects.filter(bien=bien))
    valeur = engage or float(bien.valeur_acquisition or 0)
    return {
        "valeur": round(valeur, -3),
        "intervalle": [round(valeur, -3), round(valeur, -3)],
        "methode": "Coût de construction engagé",
        "facteurs": [{"facteur": "Dépenses engagées sur le chantier" if engage else "Coût prévu du bâtiment",
                      "effet_bif": round(valeur), "effet_pct": 100.0}],
        "details": {"note": "La valeur de marché sera estimée par le modèle à la fin des travaux."},
    }


def estimer(bien: Bien):
    if bien.etat == "CONSTRUCTION":
        return _estimer_construction(bien)
    if bien.categorie in ("FON", "IMM") and bien.surface_m2:
        try:
            return _estimer_ml(bien)
        except ValueError:
            pass  # pas encore assez de ventes comparables : on se replie sur la valeur d'acquisition
    return _estimer_amortissement(bien)


def valoriser_tout(qs=None):
    qs = qs if qs is not None else Bien.objects.select_related("district", "district__organisation")
    n = 0
    for bien in qs:
        res = estimer(bien)
        bien.valeur_estimee = Decimal(res["valeur"])
        bien.methode_valorisation = res["methode"]
        bien.save(update_fields=["valeur_estimee", "methode_valorisation"])
        n += 1
    return n
