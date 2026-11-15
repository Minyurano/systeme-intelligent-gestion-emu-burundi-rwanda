"""
Analyse intelligente de la comparaison des églises (apprentissage automatique).

Le classement par « indice de bonne gestion » dit QUI est devant. Cette analyse dit POURQUOI, et QUOI FAIRE,
avec cinq méthodes complémentaires, toutes expliquées en langage simple dans la réponse :

1. Profils d'églises — regroupement automatique (K-moyennes) des églises qui se ressemblent sur l'ensemble des
   indicateurs. Le nombre de profils est choisi par le score de silhouette. Chaque profil reçoit un nom, ses forces et
   ses points à renforcer.
2. Carte des églises — analyse en composantes principales (ACP) : toutes les églises sur un plan à deux axes,
   chaque axe étant décrit par les indicateurs qui le portent. Deux églises proches sur la carte se ressemblent.
3. Indice attendu — régression ridge sur le CONTEXTE seulement (taille, patrimoine, bénéficiaires), évaluée en
   validation croisée « une église laissée de côté ». L'écart entre l'indice réel et l'indice attendu mesure ce qui
   relève de la GESTION, à contexte égal : une petite église pauvre qui fait 80 mérite plus d'éloges qu'une grande
   église riche qui fait 80.
4. Profils atypiques — réseau de neurones auto-encodeur (apprentissage profond, couches 8-3-8, moyenne de plusieurs
   réseaux) qui apprend à « résumer puis reconstruire » le profil normal d'une église. Une église mal reconstruite
   ne ressemble à aucune autre : erreur de saisie, situation exceptionnelle ou réussite à étudier.
5. Églises jumelles — plus proches voisines par le contexte. Pour chaque église, une église comparable qui fait
   mieux, et les deux ou trois points précis où elle fait mieux : une piste concrète d'entraide.

Tout est calculé à la demande, à l'intérieur d'une seule organisation et du périmètre de l'utilisateur.
Avec peu d'églises, les résultats restent indicatifs : la réponse le dit, avec des mesures de fiabilité.
"""
import hashlib
import json
import math
import warnings

import numpy as np
from django.core.cache import cache

from .comparaison import comparer

# (clé, libellé court, groupe, sens, transformation) — sens : 1 = plus haut est mieux, -1 = l'inverse, 0 = neutre
VARIABLES = [
    ("membres", "Membres", "contexte", 0, "log"),
    ("biens", "Biens recensés", "contexte", 0, "log"),
    ("valeur_par_membre", "Patrimoine par membre", "contexte", 0, "log"),
    ("beneficiaires", "Bénéficiaires des infrastructures", "contexte", 0, "log"),
    ("qualite", "Complétude des fiches", "gestion", 1, None),
    ("pct_titres", "Terrains titrés", "gestion", 1, None),
    ("pct_a_risque", "Biens à risque élevé", "gestion", -1, None),
    ("part_mauvais", "Biens en mauvais état", "gestion", -1, None),
    ("ordres_par_bien", "Travaux en attente par bien", "gestion", -1, None),
    ("taux_recouvrement", "Recouvrement des loyers", "gestion", 1, None),
    ("dons_par_membre", "Dîmes et offrandes par membre", "gestion", 1, "log"),
    ("taux_registre", "Membres inscrits au registre", "gestion", 1, None),
]
VARIABLES_DISTRICT = VARIABLES + [("declarations_30j", "Déclarations WhatsApp (30 j)", "gestion", 1, "log")]
UNITES = {"pct_titres": "%", "pct_a_risque": "%", "part_mauvais": "%", "qualite": "%", "taux_recouvrement": "%",
          "taux_registre": "%", "valeur_par_membre": "monnaie", "dons_par_membre": "monnaie", "ordres_par_bien": ""}

NOMS_PROFILS = {
    1: ["Profil unique"],
    2: ["Églises bien gérées", "Églises à accompagner"],
    3: ["Églises bien gérées", "Églises en progression", "Églises à accompagner"],
    4: ["Églises modèles", "Églises bien gérées", "Églises en progression", "Églises à accompagner"],
}
NOMS_PROFILS_DISTRICTS = {
    1: ["Profil unique"],
    2: ["Districts bien gérés", "Districts à accompagner"],
    3: ["Districts bien gérés", "Districts en progression", "Districts à accompagner"],
    4: ["Districts modèles", "Districts bien gérés", "Districts en progression", "Districts à accompagner"],
}
TRAITS_CONTEXTE = {
    "membres": ("grandes communautés", "petites communautés"),
    "biens": ("beaucoup de biens", "peu de biens"),
    "valeur_par_membre": ("patrimoine élevé par membre", "patrimoine modeste par membre"),
    "beneficiaires": ("fort impact social", "peu d'infrastructures sociales"),
}
VERSION_ANALYSE = 2


# ----------------------------------------------------------------------------------------------- outils
def _f(v, unite=""):
    """Valeur lisible pour les phrases d'interprétation."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "—"
    if unite == "%":
        return f"{round(v)} %"
    if unite == "monnaie":
        v = float(v)
        if abs(v) >= 1e6:
            return f"{v / 1e6:.1f} M".replace(".", ",")
        return f"{round(v):,}".replace(",", " ")
    if isinstance(v, float) and not v.is_integer():
        return f"{v:.1f}".replace(".", ",")
    return f"{round(v):,}".replace(",", " ")


def _preparer(lignes, variables):
    """Matrice des indicateurs : valeurs dérivées, variables trop incomplètes ou constantes écartées, médiane pour les trous."""
    brutes = []
    for l in lignes:
        biens = l.get("biens") or 0
        d = dict(l)
        d["part_mauvais"] = 100 * (l.get("mauvais") or 0) / biens if biens else None
        d["ordres_par_bien"] = (l.get("ordres_ouverts") or 0) / biens if biens else None
        brutes.append(d)

    gardees, colonnes, ecartees = [], [], []
    for cle, lib, groupe, sens, transfo in variables:
        vals = [d.get(cle) for d in brutes]
        presentes = [float(v) for v in vals if v is not None]
        if len(presentes) < max(3, math.ceil(0.5 * len(vals))):
            ecartees.append({"libelle": lib, "raison": "trop peu de données renseignées"})
            continue
        if np.std(presentes) < 1e-9:
            ecartees.append({"libelle": lib, "raison": "même valeur partout, rien à comparer"})
            continue
        if UNITES.get(cle) == "%" and max(presentes) - min(presentes) < 5:
            ecartees.append({"libelle": lib, "raison": "écarts de moins de 5 points, trop faibles pour distinguer les entités"})
            continue
        med = float(np.median(presentes))
        col = np.array([float(v) if v is not None else med for v in vals])
        if transfo == "log":
            col = np.log1p(np.clip(col, 0, None))
        colonnes.append(col)
        gardees.append({"cle": cle, "libelle": lib, "groupe": groupe, "sens": sens, "unite": UNITES.get(cle, ""),
                        "completes": len(presentes), "total": len(vals)})
    X = np.column_stack(colonnes) if colonnes else np.zeros((len(lignes), 0))
    return brutes, X, gardees, ecartees


def _moyenne(brutes, cle, indices=None):
    vals = [brutes[i].get(cle) for i in (indices if indices is not None else range(len(brutes)))]
    vals = [float(v) for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


# ----------------------------------------------------------------------------------------------- 1. profils
def _profils(Z, brutes, variables, mot="Églises"):
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    n = len(Z)
    if n < 4:
        return None, None, {"k": 0, "silhouette": None, "texte": "Il faut au moins 4 entités pour former des profils."}
    essais = []
    for k in range(2, min(4, n - 1) + 1):
        km = KMeans(n_clusters=k, n_init=20, random_state=0).fit(Z)
        if len(set(km.labels_)) < k:
            continue
        s = float(silhouette_score(Z, km.labels_))
        # Un profil d'une seule église n'est gardé que si le découpage est nettement meilleur
        if min(np.bincount(km.labels_)) == 1:
            s -= 0.05
        essais.append((k, s, km.labels_))
    etiquettes, silhouette, k = None, 0.0, 1
    if essais:
        top = max(s for _, s, _ in essais)
        # Parmi les découpages presque aussi bons que le meilleur, on garde le plus détaillé (plus utile pour agir)
        k, silhouette, etiquettes = max((e for e in essais if e[1] >= top - 0.06), key=lambda e: e[0])
    if etiquettes is None:
        etiquettes, silhouette, k = np.zeros(n, dtype=int), 0.0, 1

    # Ordre des profils : du meilleur indice moyen au plus faible (le nom suit cet ordre)
    ind = np.array([b.get("indice") if b.get("indice") is not None else np.nan for b in brutes], dtype=float)
    moy = {c: np.nanmean(ind[etiquettes == c]) if np.any(~np.isnan(ind[etiquettes == c])) else -1 for c in set(etiquettes)}
    ordre = sorted(moy, key=lambda c: -moy[c])
    renum = {ancien: nouveau for nouveau, ancien in enumerate(ordre)}
    etiquettes = np.array([renum[c] for c in etiquettes])
    noms = (NOMS_PROFILS if mot == "Églises" else NOMS_PROFILS_DISTRICTS)[k]

    profils = []
    for c in range(k):
        idx = np.where(etiquettes == c)[0]
        centre = Z[idx].mean(axis=0)
        traits = []
        for j, v in enumerate(variables):
            z = float(centre[j])
            traits.append({**{x: v[x] for x in ("cle", "libelle", "groupe", "sens", "unite")}, "z": round(z, 2),
                           "z_oriente": round(z * v["sens"], 2) if v["sens"] else None,
                           "valeur_profil": _moyenne(brutes, v["cle"], idx), "valeur_globale": _moyenne(brutes, v["cle"])})
        gestion = [t for t in traits if t["z_oriente"] is not None]
        forces = sorted([t for t in gestion if t["z_oriente"] >= 0.25], key=lambda t: -t["z_oriente"])[:3]
        faibles = sorted([t for t in gestion if t["z_oriente"] <= -0.25], key=lambda t: t["z_oriente"])[:3]
        contexte = sorted([t for t in traits if t["groupe"] == "contexte" and abs(t["z"]) >= 0.7], key=lambda t: -abs(t["z"]))
        descripteur = TRAITS_CONTEXTE[contexte[0]["cle"]][0 if contexte[0]["z"] > 0 else 1] if contexte else None
        nom = noms[c] + (f" · {descripteur}" if descripteur and k > 1 else "")
        texte_force = lambda t: f"{t['libelle']} : {_f(t['valeur_profil'], t['unite'])} (moyenne {_f(t['valeur_globale'], t['unite'])})"
        membres = sorted((brutes[i]["nom"] for i in idx))
        indice_moyen = round(moy[ordre[c]]) if moy[ordre[c]] >= 0 else None
        if k == 1:
            description = "Les entités se ressemblent trop pour former des groupes distincts."
        else:
            description = (f"{len(idx)} {'entité' if len(idx) == 1 else 'entités'}, indice moyen {indice_moyen}/100. "
                           + (f"Elles se distinguent surtout par : {', '.join(t['libelle'].lower() for t in (forces + faibles)[:3])}."
                              if forces or faibles else "Elles sont proches de la moyenne sur la plupart des indicateurs."))
        profils.append({"id": c, "nom": nom, "effectif": len(idx), "membres": membres, "indice_moyen": indice_moyen,
                        "traits": traits, "forces": [texte_force(t) for t in forces],
                        "faiblesses": [texte_force(t) for t in faibles], "description": description})

    if k == 1:
        lecture = f"Pas de groupes nets : les {mot.lower()} ont des profils voisins."
    elif silhouette >= 0.5:
        lecture = "Groupes très nets : les profils sont bien séparés."
    elif silhouette >= 0.25:
        lecture = f"Groupes assez nets : la plupart des {mot.lower()} appartiennent clairement à un profil."
    else:
        lecture = "Groupes peu marqués : certains éléments sont à la frontière de deux profils ; à lire comme une tendance."
    qualite = {"k": k, "silhouette": round(silhouette, 2), "texte": lecture}
    return etiquettes, profils, qualite


# ----------------------------------------------------------------------------------------------- 2. carte
def _axe_texte(chargements, variables):
    ordre = np.argsort(-np.abs(chargements))[:3]
    hauts = [variables[j]["libelle"].lower() for j in ordre if chargements[j] > 0]
    bas = [variables[j]["libelle"].lower() for j in ordre if chargements[j] < 0]
    morceaux = []
    if hauts:
        morceaux.append("valeurs plus élevées pour " + ", ".join(hauts))
    if bas:
        morceaux.append("plus faibles pour " + ", ".join(bas))
    return variables[ordre[0]]["libelle"], ", ".join(morceaux)


def _carte(Z, brutes, variables, etiquettes):
    from sklearn.decomposition import PCA

    if len(Z) < 3 or Z.shape[1] < 2:
        return None
    pca = PCA(n_components=2, random_state=0).fit(Z)
    coords = pca.transform(Z)
    axes = {}
    for nom_axe, i, cote in (("x", 0, ("Vers la droite", "vers la gauche")), ("y", 1, ("Vers le haut", "vers le bas"))):
        ch = pca.components_[i]
        # Orientation lisible : l'indicateur le plus lourd tire vers la droite (ou le haut)
        if ch[np.argmax(np.abs(ch))] < 0:
            ch, coords[:, i] = -ch, -coords[:, i]
        principal, desc = _axe_texte(ch, variables)
        axes[nom_axe] = {"libelle": f"Axe {i + 1} : surtout « {principal} »", "variance": round(100 * float(pca.explained_variance_ratio_[i])),
                         "texte": f"{cote[0]} : {desc} ; {cote[1]} : l'inverse."}
    points = [{"id": b["id"], "nom": b["nom"], "x": round(float(coords[i, 0]), 3), "y": round(float(coords[i, 1]), 3),
               "profil": int(etiquettes[i]) if etiquettes is not None else 0, "indice": b.get("indice")} for i, b in enumerate(brutes)]
    total = axes["x"]["variance"] + axes["y"]["variance"]
    return {"points": points, "axes": axes, "variance_totale": total,
            "lecture": f"Chaque point est une église. Deux points proches = deux églises qui se ressemblent sur l'ensemble des "
                       f"indicateurs. Les deux axes résument {total} % des différences entre églises"
                       + (" : la carte est fidèle." if total >= 60 else " : la carte simplifie, à compléter par les profils.")}


# ----------------------------------------------------------------------------------------------- 3. indice attendu
def _attendu(brutes, X, variables):
    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import LeaveOneOut, cross_val_predict
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    ctx = [j for j, v in enumerate(variables) if v["groupe"] == "contexte"]
    ok = [i for i, b in enumerate(brutes) if b.get("indice") is not None]
    if len(ok) < 6 or not ctx:
        return {"disponible": False, "raison": "Il faut au moins 6 entités avec un indice pour estimer un indice attendu."}
    Xc, y = X[np.ix_(ok, ctx)], np.array([brutes[i]["indice"] for i in ok], dtype=float)
    modele = make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-1, 3, 20)))
    pred = np.clip(cross_val_predict(modele, Xc, y, cv=LeaveOneOut()), 0, 100)
    r2 = 1 - float(np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)) if np.var(y) > 0 else 0.0
    reference = "contexte"
    if r2 < 0.15:
        # Le contexte ne prédit rien de fiable : on compare honnêtement à la moyenne des AUTRES entités
        pred = np.array([(y.sum() - y[i]) / (len(y) - 1) for i in range(len(y))])
        reference = "moyenne"
    lignes = []
    for pos, i in enumerate(ok):
        reel, att = int(y[pos]), int(round(pred[pos]))
        ecart = reel - att
        repere = "une église de même contexte" if reference == "contexte" else "la moyenne des autres"
        if ecart >= 10:
            texte = f"Fait nettement mieux que {repere} ({reel} contre {att}) : bonne pratique à partager."
        elif ecart <= -10:
            texte = f"En dessous de {repere} ({reel} contre {att}) : marge de progrès réelle, à accompagner."
        else:
            texte = f"Proche de {repere} ({reel} contre {att})."
        lignes.append({"id": brutes[i]["id"], "nom": brutes[i]["nom"], "reel": reel, "attendu": att, "ecart": ecart, "texte": texte})
    lignes.sort(key=lambda l: -l["ecart"])
    if r2 < 0.15:
        lecture = ("Le contexte (taille, patrimoine, bénéficiaires) n'explique presque pas les différences d'indice : "
                   "les écarts viennent surtout de la façon de gérer, et chaque église est donc comparée à la moyenne des autres. "
                   "Bonne nouvelle : une petite ou une pauvre église peut aussi bien gérer qu'une grande.")
    elif r2 < 0.5:
        lecture = "Le contexte explique une partie des différences ; l'autre partie relève de la gestion."
    else:
        lecture = "Le contexte explique une grande partie des différences : comparez surtout des églises de contexte proche."
    return {"disponible": True, "r2": round(max(r2, 0.0), 2), "reference": reference, "lignes": lignes, "lecture": lecture,
            "variables": [variables[j]["libelle"] for j in ctx]}


# ----------------------------------------------------------------------------------------------- 4. atypiques
def _atypiques(Z, brutes, variables):
    from sklearn.neural_network import MLPRegressor

    n, p = Z.shape
    if n < 6 or p < 3:
        return {"disponible": False, "raison": "Il faut au moins 6 entités et 3 indicateurs pour entraîner le réseau de neurones."}
    from sklearn.model_selection import KFold

    goulot = max(2, min(3, p - 1))
    # Chaque église est reconstruite par des réseaux entraînés SANS elle (validation croisée) : sinon le réseau
    # apprendrait par cœur une église hors norme et ne la signalerait jamais. Moyenne de 3 réseaux par pli : stable.
    R = np.zeros_like(Z)
    plis = KFold(n_splits=min(5, n), shuffle=True, random_state=0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for apprentissage, test in plis.split(Z):
            sorties = []
            for graine in range(3):
                ae = MLPRegressor(hidden_layer_sizes=(8, goulot, 8), activation="tanh", solver="lbfgs", alpha=0.05,
                                  max_iter=3000, random_state=graine)
                ae.fit(Z[apprentissage], Z[apprentissage])
                sorties.append(ae.predict(Z[test]))
            R[test] = np.mean(sorties, axis=0)
    residus = Z - R
    erreurs = np.sqrt(np.mean(residus ** 2, axis=1))
    q1, med, q3 = np.percentile(erreurs, [25, 50, 75])
    seuil = float(max(q3 + 1.5 * (q3 - q1), 2 * med))
    fidelite = 1 - float(np.sum(residus ** 2) / np.sum(Z ** 2)) if np.sum(Z ** 2) > 0 else 0.0
    lignes = []
    for i, b in enumerate(brutes):
        contributions = np.argsort(-np.abs(residus[i]))[:2]
        raisons = []
        for j in contributions:
            v = variables[j]
            plus = residus[i, j] > 0
            reel = b.get(v["cle"])
            sens_txt = "beaucoup plus élevé" if plus else "beaucoup plus faible"
            raisons.append(f"{v['libelle']} : {_f(reel, v['unite'])}, {sens_txt} que ce que son profil laisse attendre")
        atypique = bool(erreurs[i] > seuil)
        lignes.append({"id": b["id"], "nom": b["nom"], "score": round(float(100 * erreurs[i] / max(erreurs.max(), 1e-9))),
                       "erreur": round(float(erreurs[i]), 3), "atypique": atypique, "raisons": raisons if atypique else raisons[:1]})
    lignes.sort(key=lambda l: -l["erreur"])
    nb = sum(l["atypique"] for l in lignes)
    note = ("" if fidelite >= 0.3 else " Avec si peu d'entités, le réseau reconstruit mal toutes les églises : "
            "le classement ci-dessous est une indication, pas une alerte.")
    return {"disponible": True, "seuil_score": round(100 * seuil / max(erreurs.max(), 1e-9)), "fidelite": round(max(fidelite, 0.0), 2),
            "note": note.strip(),
            "nombre": nb, "lignes": lignes,
            "lecture": ("Aucune église ne sort du lot : les profils sont cohérents entre eux." if nb == 0 else
                        f"{nb} {'église ne ressemble' if nb == 1 else 'églises ne ressemblent'} à aucune autre. "
                        "Atypique ne veut pas dire mauvais : vérifiez d'abord les données saisies, puis cherchez la raison "
                        "(situation exceptionnelle, ou réussite à étudier).")}


# ----------------------------------------------------------------------------------------------- 5. jumelles
def _jumelles(Z, brutes, variables):
    from sklearn.neighbors import NearestNeighbors

    ctx = [j for j, v in enumerate(variables) if v["groupe"] == "contexte"]
    gest = [j for j, v in enumerate(variables) if v["groupe"] == "gestion"]
    n = len(brutes)
    if n < 3 or not ctx or not gest:
        return []
    k = min(n, 5)
    nn = NearestNeighbors(n_neighbors=k).fit(Z[:, ctx])
    distances, voisins = nn.kneighbors(Z[:, ctx])
    echelle = float(np.median(distances[:, 1:])) or 1.0
    resultat = []
    for i, b in enumerate(brutes):
        if b.get("indice") is None:
            continue
        candidat = None
        for d, j in zip(distances[i][1:], voisins[i][1:]):
            autre = brutes[j]
            if autre.get("indice") is not None and autre["indice"] >= b["indice"] + 5:
                candidat = (d, j)
                break
        if candidat is None:
            continue
        d, j = candidat
        modele = brutes[j]
        ecarts = sorted(((float((Z[j, g] - Z[i, g]) * variables[g]["sens"]), g) for g in gest), reverse=True)
        lecons = []
        for gain, g in ecarts:
            if gain < 0.3 or len(lecons) >= 3:
                break
            v = variables[g]
            # Pas de leçon sur un indicateur que l'une des deux églises n'a pas (ex. aucun terrain, donc pas de taux de titres)
            if b.get(v["cle"]) is None or modele.get(v["cle"]) is None:
                continue
            lecons.append(f"{v['libelle']} : {_f(b.get(v['cle']), v['unite'])} contre {_f(modele.get(v['cle']), v['unite'])}")
        if not lecons:
            continue
        similarite = max(0, min(100, round(100 * math.exp(-d / (2 * echelle)))))
        resultat.append({"id": b["id"], "nom": b["nom"], "indice": b["indice"],
                         "modele": {"id": modele["id"], "nom": modele["nom"], "indice": modele["indice"], "similarite": similarite},
                         "lecons": lecons,
                         "texte": f"{b['nom']} peut s'inspirer de {modele['nom']} : contexte comparable ({similarite} % de ressemblance), "
                                  f"mais {modele['indice'] - b['indice']} points d'indice de plus."})
    resultat.sort(key=lambda r: r["indice"])
    return resultat


# ----------------------------------------------------------------------------------------------- synthèse
def _resume(profils, attendu, atypiques, jumelles, niveau):
    nom = "église" if niveau == "paroisse" else "district"
    phrases = []
    if profils and len(profils) > 1:
        phrases.append(f"Les {nom}s se répartissent en {len(profils)} profils : "
                       + " ; ".join(f"« {p['nom']} » ({p['effectif']})" for p in profils) + ".")
        bas = profils[-1]
        if bas["faiblesses"]:
            phrases.append(f"Pour le profil « {bas['nom']} », la priorité est : {bas['faiblesses'][0].split(' :')[0].lower()}.")
    if attendu and attendu.get("disponible"):
        top = [l for l in attendu["lignes"] if l["ecart"] >= 10]
        bas = [l for l in attendu["lignes"] if l["ecart"] <= -10]
        if top:
            debut = "À contexte égal" if attendu.get("reference") == "contexte" else "Par rapport à la moyenne"
            phrases.append(f"{debut}, {top[0]['nom']} fait le mieux (+{top[0]['ecart']} points) : une expérience à partager.")
        if bas:
            phrases.append(f"{bas[-1]['nom']} a la plus grande marge de progrès ({bas[-1]['ecart']} points).")
    if atypiques and atypiques.get("disponible") and atypiques["nombre"]:
        a = [l["nom"] for l in atypiques["lignes"] if l["atypique"]]
        phrases.append(f"Profil atypique à vérifier : {', '.join(a)}.")
    if jumelles:
        j = jumelles[0]
        phrases.append(f"Jumelage suggéré : {j['nom']} avec {j['modele']['nom']}.")
    return phrases


def _fiabilite(n):
    if n < 6:
        return {"niveau": "faible", "texte": f"Seulement {n} entités : les résultats sont des pistes, pas des conclusions."}
    if n < 20:
        return {"niveau": "indicative", "texte": f"{n} entités : résultats indicatifs, à confirmer par la connaissance du terrain."}
    return {"niveau": "bonne", "texte": f"{n} entités : résultats solides, à confronter quand même au terrain."}


METHODE = [
    {"titre": "Profils (K-moyennes)", "texte": "Regroupe automatiquement les églises qui se ressemblent sur tous les indicateurs à la fois. "
     "Le nombre de groupes est choisi par l'ordinateur (score de silhouette)."},
    {"titre": "Carte (analyse en composantes principales)", "texte": "Résume une douzaine d'indicateurs en deux axes pour pouvoir les dessiner. "
     "Chaque axe est décrit par les indicateurs qui pèsent le plus."},
    {"titre": "Indice attendu (régression ridge, validation croisée)", "texte": "Estime l'indice qu'aurait une église d'après son seul contexte "
     "(taille, patrimoine, bénéficiaires), sans jamais utiliser l'église elle-même pour apprendre. L'écart mesure la part due à la gestion."},
    {"titre": "Profils atypiques (réseau de neurones auto-encodeur)", "texte": "Un réseau de neurones apprend, sur les autres églises, à résumer "
     "puis reconstruire le profil « normal » d'une église. Celles qu'il reconstruit mal ne ressemblent à aucune autre."},
    {"titre": "Églises jumelles (plus proches voisins)", "texte": "Trouve, pour chaque église, une église de contexte proche qui fait mieux, "
     "et montre précisément sur quels points."},
]


def analyser(organisation_id, niveau="paroisse", district_id=None, annee=None):
    donnees = comparer(organisation_id, niveau, district_id, annee)
    lignes = donnees["lignes"]
    cle = "ml:" + hashlib.sha256(json.dumps([VERSION_ANALYSE, niveau, lignes], sort_keys=True, default=str).encode()).hexdigest()
    deja = cache.get(cle)
    if deja is not None:
        return deja
    resultat = _analyser(lignes, niveau, donnees["annee"])
    cache.set(cle, resultat, 3600)
    return resultat


def _analyser(lignes, niveau, annee):
    from sklearn.preprocessing import StandardScaler

    base = {"niveau": niveau, "annee": annee, "n": len(lignes), "fiabilite": _fiabilite(len(lignes)), "methode": METHODE}
    if len(lignes) < 3:
        return {**base, "disponible": False, "raison": "Il faut au moins 3 entités dans votre périmètre pour une analyse."}
    brutes, X, variables, ecartees = _preparer(lignes, VARIABLES_DISTRICT if niveau == "district" else VARIABLES)
    if X.shape[1] < 2:
        return {**base, "disponible": False, "raison": "Pas assez d'indicateurs renseignés pour une analyse."}
    Z = StandardScaler().fit_transform(X)

    etiquettes, profils, qualite = _profils(Z, brutes, variables, "Églises" if niveau == "paroisse" else "Districts")
    carte = _carte(Z, brutes, variables, etiquettes)
    attendu = _attendu(brutes, X, variables)
    atypiques = _atypiques(Z, brutes, variables)
    jumelles = _jumelles(Z, brutes, variables)
    return {**base, "disponible": True, "variables": variables, "variables_ecartees": ecartees,
            "resume": _resume(profils, attendu, atypiques, jumelles, niveau),
            "profils": profils, "qualite_profils": qualite, "carte": carte, "attendu": attendu,
            "atypiques": atypiques, "jumelles": jumelles}
