"""
Compréhension d'un message de terrain (WhatsApp, SMS, dictée).

Exemple : « Nouveau forage à Muyange, en bon état, financé par UMCOR, 45 000 000 BIF »
devient : catégorie INF, type « Forage », paroisse Muyange, état BON, financeur UMCOR,
valeur 45 000 000.

La méthode est volontairement simple et explicable (mots-clés + expressions régulières) :
elle fonctionne hors connexion, sans coût, et le responsable corrige ce qui manque avant
de valider. Le vocabulaire kirundi ci-dessous est un point de départ à faire compléter et
valider par des locuteurs natifs.
"""
import re
import unicodedata

from core.models import Paroisse


def normaliser(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


# (mots-clés, catégorie, type précis) — du plus précis au plus général
TYPES = [
    (["centre de sante", "dispensaire", "ivuriro"], "IMM", "Centre de santé"),
    (["ecole", "ishure", "lycee"], "IMM", "École"),
    (["eglise", "temple", "chapelle", "urusengero"], "IMM", "Église"),
    (["maison", "presbytere", "bureau", "batiment"], "IMM", "Bâtiment"),
    (["forage", "puits", "iriba", "source d'eau", "pompe"], "INF", "Forage"),
    (["panneau solaire", "panneaux solaires", "solaire"], "INF", "Installation solaire"),
    (["usine", "moulin"], "INF", "Usine"),
    (["terrain", "parcelle", "isambu"], "FON", "Terrain"),
    (["machine a coudre", "machines a coudre"], "EQP", "Machine à coudre"),
    (["ordinateur", "ordinateurs", "imprimante"], "EQP", "Matériel informatique"),
    (["groupe electrogene", "generateur"], "EQP", "Groupe électrogène"),
    (["chaise", "chaises", "banc", "bancs", "table", "tables"], "EQP", "Mobilier"),
    (["moto", "motos", "ipikipiki"], "VEH", "Moto"),
    (["voiture", "vehicule", "camion", "pick-up", "imodoka"], "VEH", "Véhicule"),
    (["chevre", "chevres", "ihene"], "AGR", "Chèvres"),
    (["porc", "porcs", "cochon", "porcherie", "ingurube"], "AGR", "Porcs"),
    (["vache", "vaches", "inka"], "AGR", "Bovins"),
    (["poule", "poules", "inkoko"], "AGR", "Volaille"),
    (["champ", "champs", "plantation"], "AGR", "Champ"),
]

ETATS = [
    (["en construction", "chantier", "inachevé", "inacheve"], "CONSTRUCTION"),
    (["panne", "casse", "cassee", "mauvais", "mauvaise", "abime", "abimee", "fuite", "effondre", "ne marche pas", "mbi"], "MAUVAIS"),
    (["moyen", "moyenne", "use", "usee", "a reparer", "vieux", "vieille"], "MOYEN"),
    (["bon", "bonne", "neuf", "neuve", "fonctionne", "marche bien", "nziza"], "BON"),
]

FINANCEURS = ["UMCOR", "GBGM", "UMDA", "YAI", "Global Ministries", "Health Board", "Imagine No Malaria"]

COMMANDES_AIDE = {"aide", "help", "menu", "?", "ubufasha"}


def _nombre(texte):
    return float(re.sub(r"[\s. ]", "", texte).replace(",", "."))


def interpreter(texte, organisation, district=None):
    """Renvoie les champs reconnus, ce qui manque, et un indice de confiance entre 0 et 1."""
    t = normaliser(texte)
    res = {"categorie": None, "sous_type": None, "etat": None, "paroisse": None, "paroisse_nom": None,
           "quantite": 1, "valeur_acquisition": None, "financeur": "", "surface_m2": None, "nom": ""}

    for mots, cat, st in TYPES:
        if any(re.search(rf"\b{re.escape(m)}\b", t) for m in mots):
            res["categorie"], res["sous_type"] = cat, st
            break
    for mots, etat in ETATS:
        if any(re.search(rf"\b{re.escape(m)}\b", t) for m in mots):
            res["etat"] = etat
            break

    paroisses = Paroisse.objects.filter(district__organisation=organisation)
    if district:
        paroisses = sorted(paroisses, key=lambda p: p.district_id != district.pk)  # celles du district d'abord
    for p in paroisses:
        if re.search(rf"\b{re.escape(normaliser(p.nom))}\b", t):
            res["paroisse"], res["paroisse_nom"], res["district"] = p.pk, p.nom, p.district_id
            break

    devises = "bif|fbu|francs?|frw|rwf|ksh|kes|ugx|usd|dollars?|\\$|" + organisation.devise.lower()
    m = re.search(rf"(\d[\d\s. ,]*\d|\d)\s*(millions?|m)?\s*({devises})\b", t)
    if m:
        v = _nombre(m.group(1)) * (1_000_000 if m.group(2) else 1)
        if m.group(3) in ("usd", "dollar", "dollars", "$"):
            v *= organisation.taux_usd
        res["valeur_acquisition"] = round(v)
    m = re.search(r"(\d[\d\s.]*)\s*(m2|m²|metres? carres?|hectares?|ha)\b", t)
    if m:
        s = _nombre(m.group(1))
        res["surface_m2"] = s * 10_000 if m.group(2).startswith("h") else s
    m = re.search(r"\b(\d{1,4})\s+(?!m2|ha|millions?|bif|fbu|francs?|rwf|usd)([a-z]+)", t)
    if m and res["categorie"] in ("EQP", "AGR", "VEH"):
        res["quantite"] = int(m.group(1))

    for f in FINANCEURS:
        if normaliser(f) in t:
            res["financeur"] = f
            break

    if res["sous_type"]:
        res["nom"] = res["sous_type"] + (f" de {res['paroisse_nom']}" if res["paroisse_nom"] else "")
    else:
        premiere = re.split(r"[.,\n]", texte.strip())[0]
        res["nom"] = premiere[:80]

    # Le message parle-t-il d'un bien déjà inventorié ? (même type au même endroit)
    from .models import Bien

    if res["sous_type"] and res["paroisse"]:
        mot = normaliser(res["sous_type"]).split()[0][:5]
        for b in Bien.objects.filter(paroisse_id=res["paroisse"]):
            if mot in normaliser(b.sous_type) or mot in normaliser(b.nom):
                res["bien_existant"] = {"id": b.pk, "code": b.code, "nom": b.nom, "etat": b.etat}
                break

    attendus = {"categorie": "le type de bien", "etat": "l'état", "paroisse": "le lieu (paroisse)"}
    res["manquants"] = [lib for champ, lib in attendus.items() if not res[champ]]
    res["confiance"] = round(1 - len(res["manquants"]) / (len(attendus) + 1), 2)
    return res


def resumer(interp, devise):
    """Phrase de confirmation renvoyée à l'expéditeur."""
    morceaux = [interp["nom"] or "Bien"]
    if interp["etat"]:
        morceaux.append({"BON": "en bon état", "MOYEN": "en état moyen", "MAUVAIS": "en mauvais état",
                         "CONSTRUCTION": "en construction"}[interp["etat"]])
    if interp["quantite"] and interp["quantite"] > 1:
        morceaux.append(f"{interp['quantite']} unités")
    if interp["valeur_acquisition"]:
        morceaux.append(f"{interp['valeur_acquisition']:,.0f} {devise}".replace(",", " "))
    return ", ".join(morceaux)
