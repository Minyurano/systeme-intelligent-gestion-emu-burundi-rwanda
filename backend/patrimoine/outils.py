"""
Outils d'adoption et d'interopérabilité :
- import d'un inventaire existant (Excel ou CSV), avec aperçu et rapport d'erreurs ;
- export des projets au standard international IATI (transparence de l'aide) ;
- export comptable des transactions ;
- score de qualité des données et classement des districts.
"""
import csv
import io
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

from django.db import transaction
from django.db.models import Max
from django.http import HttpResponse
from rest_framework.decorators import api_view, parser_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from core.models import District, JournalAction, Paroisse, Profil
from core.securite import profil_de
from finances.models import Transaction

from .models import Bien, Declaration, Mouvement, Projet
from .serializers import BienSerializer
from . import cache_donnees

R = Profil.Role


def _norm(t):
    t = unicodedata.normalize("NFD", str(t or "").strip().lower())
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in t if unicodedata.category(c) != "Mn")).strip()


# ------------------------------------------------------------------ Import

COLONNES = {
    "nom": ["nom", "nom du bien", "designation", "libelle", "bien", "name"],
    "categorie": ["categorie", "category", "type de bien", "famille"],
    "sous_type": ["type", "type precis", "sous type", "nature"],
    "district": ["district", "region", "diocese"],
    "paroisse": ["paroisse", "parish", "eglise locale", "localite", "lieu"],
    "etat": ["etat", "condition", "state"],
    "statut_juridique": ["statut juridique", "titre", "titre foncier", "juridique"],
    "surface_m2": ["surface", "surface m2", "superficie", "superficie m2", "area"],
    "quantite": ["quantite", "nombre", "qte", "quantity"],
    "date_acquisition": ["date acquisition", "date d acquisition", "annee", "annee d acquisition", "acquisition"],
    "valeur_acquisition": ["valeur", "valeur acquisition", "valeur d acquisition", "cout", "prix", "montant", "value"],
    "latitude": ["latitude", "lat"],
    "longitude": ["longitude", "lon", "lng", "long"],
    "financeur": ["financeur", "bailleur", "donateur", "funder"],
    "beneficiaires": ["beneficiaires", "beneficiaries"],
    "responsable": ["responsable", "gestionnaire"],
    "description": ["description", "observations", "remarques", "commentaire"],
}
VALEURS_CATEGORIE = {
    "FON": ["fon", "foncier", "terrain", "parcelle", "land"],
    "IMM": ["imm", "immobilier", "batiment", "eglise", "ecole", "centre de sante", "maison", "building"],
    "INF": ["inf", "infrastructure", "forage", "puits", "usine"],
    "EQP": ["eqp", "equipement", "materiel", "mobilier", "equipment"],
    "VEH": ["veh", "vehicule", "moto", "voiture", "vehicle"],
    "AGR": ["agr", "agricole", "elevage", "betail", "champ"],
}
VALEURS_ETAT = {"BON": ["bon", "bien", "neuf", "good"], "MOYEN": ["moyen", "passable", "fair"],
                "MAUVAIS": ["mauvais", "panne", "bad", "poor"], "CONSTRUCTION": ["construction", "chantier", "en construction"]}
VALEURS_JURIDIQUE = {"TITRE": ["titre", "titre de propriete", "oui", "titre foncier", "yes"],
                     "EN_COURS": ["en cours", "demarches en cours", "demarche"], "SANS_TITRE": ["sans titre", "non", "aucun", "no"],
                     "NA": ["na", "non applicable", ""]}


def _choix(valeur, table, defaut=None):
    v = _norm(valeur)
    for code, mots in table.items():
        if v == code.lower() or v in mots or any(v.startswith(m) for m in mots if m):
            return code
    return defaut


def _lire(fichier):
    """Renvoie (en-têtes, lignes) d'un fichier Excel ou CSV."""
    nom = fichier.name.lower()
    if nom.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        ws = load_workbook(fichier, read_only=True, data_only=True).active
        lignes = [list(r) for r in ws.iter_rows(values_only=True)]
    elif nom.endswith(".csv") or nom.endswith(".txt"):
        texte = fichier.read().decode("utf-8-sig", errors="replace")
        sep = ";" if texte.count(";") > texte.count(",") else ","
        lignes = list(csv.reader(io.StringIO(texte), delimiter=sep))
    else:
        raise ValidationError("Format non reconnu : envoyez un fichier Excel (.xlsx) ou CSV.")
    lignes = [l for l in lignes if any(c not in (None, "") for c in l)]
    if len(lignes) < 2:
        raise ValidationError("Le fichier ne contient pas de lignes de données.")
    return lignes[0], lignes[1:]


def _date(v):
    if isinstance(v, (datetime, date)):
        return (v.date() if isinstance(v, datetime) else v).isoformat()
    s = str(v or "").strip()
    if re.fullmatch(r"\d{4}(\.0)?", s):
        return f"{int(float(s))}-01-01"
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _nombre(v):
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return v
    s = re.sub(r"[^\d,.\-]", "", str(v)).replace(",", ".")
    if s.count(".") > 1:
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


@api_view(["POST"])
@parser_classes([MultiPartParser])
def importer_biens(request):
    """
    Importe un inventaire existant. `apercu=1` analyse sans rien enregistrer.
    Les lignes valides sont importées ; les autres sont listées avec la raison du refus.
    """
    profil = profil_de(request.user)
    if profil.role not in (R.ADMIN, R.SURINTENDANT, R.AGENT):
        raise PermissionDenied("L'import est réservé aux administrateurs, surintendants et agents.")
    f = request.FILES.get("fichier")
    if not f:
        raise ValidationError({"fichier": "Joignez un fichier Excel ou CSV."})
    entetes, lignes = _lire(f)
    correspondance, ignorees = {}, []
    for i, e in enumerate(entetes):
        n = _norm(e)
        champ = next((c for c, syn in COLONNES.items() if n in syn), None)
        if champ and champ not in correspondance.values():
            correspondance[i] = champ
        elif e not in (None, ""):
            ignorees.append(str(e))
    if "nom" not in correspondance.values():
        raise ValidationError("Colonne « Nom » introuvable. Téléchargez le modèle d'import pour voir les colonnes attendues.")

    districts = {_norm(d.nom): d for d in District.objects.filter(organisation_id=profil.organisation_id)}
    districts.update({_norm(d.code): d for d in list(districts.values())})
    districts.update({_norm(d.siege): d for d in list(districts.values()) if d.siege})
    paroisses = {}
    for p in Paroisse.objects.filter(district__organisation_id=profil.organisation_id):
        paroisses.setdefault(_norm(p.nom), p)

    resultats, valides = [], []
    for num, l in enumerate(lignes, start=2):
        brut = {champ: l[i] if i < len(l) else None for i, champ in correspondance.items()}
        erreurs = []
        par = paroisses.get(_norm(brut.get("paroisse"))) if brut.get("paroisse") else None
        dist = districts.get(_norm(brut.get("district"))) if brut.get("district") else None
        if dist is None and par is not None:
            dist = par.district  # le district se déduit de la paroisse
        if not profil.voit_tout:
            dist = profil.district if dist is None or dist.pk == profil.district_id else dist
        if dist is None:
            erreurs.append(f"district « {brut.get('district') or 'vide'} » inconnu")
        cat = _choix(brut.get("categorie") or brut.get("sous_type"), VALEURS_CATEGORIE)
        if cat is None:
            erreurs.append(f"catégorie « {brut.get('categorie') or 'vide'} » non reconnue")
        donnees = {
            "nom": str(brut.get("nom") or "").strip(), "categorie": cat, "sous_type": str(brut.get("sous_type") or "")[:80],
            "district": dist.pk if dist else None, "paroisse": par.pk if par and dist and par.district_id == dist.pk else None,
            "etat": _choix(brut.get("etat"), VALEURS_ETAT, "BON"),
            "statut_juridique": _choix(brut.get("statut_juridique"), VALEURS_JURIDIQUE, "TITRE" if cat == "FON" and brut.get("statut_juridique") else "NA"),
            "surface_m2": _nombre(brut.get("surface_m2")), "quantite": int(_nombre(brut.get("quantite")) or 1),
            "date_acquisition": _date(brut.get("date_acquisition")), "valeur_acquisition": round(_nombre(brut.get("valeur_acquisition")) or 0),
            "latitude": _nombre(brut.get("latitude")), "longitude": _nombre(brut.get("longitude")),
            "financeur": str(brut.get("financeur") or "")[:120], "beneficiaires": int(_nombre(brut.get("beneficiaires")) or 0),
            "responsable": str(brut.get("responsable") or "")[:120], "description": str(brut.get("description") or ""),
        }
        if not erreurs:
            s = BienSerializer(data=donnees)
            if s.is_valid():
                if not profil.voit_tout and dist.pk != profil.district_id:
                    erreurs.append("hors de votre district")
                else:
                    valides.append(s)
            else:
                erreurs += [f"{k} : {' '.join(map(str, v))}" for k, v in s.errors.items()]
        resultats.append({"ligne": num, "nom": donnees["nom"], "categorie": cat, "district": dist.nom if dist else None,
                          "etat": donnees["etat"], "valeur": donnees["valeur_acquisition"], "erreurs": erreurs})

    crees = 0
    if request.data.get("apercu") not in ("1", "true", "oui") and valides:
        from ia import predictions, valorisation

        with transaction.atomic():
            for s in valides:
                b = s.save()
                Mouvement.objects.create(bien=b, type="ACQUISITION", date=b.date_acquisition or date.today(),
                                         montant=b.valeur_acquisition, description="Importé depuis un fichier", auteur=request.user.username)
                try:
                    res = valorisation.estimer(b)
                    b.valeur_estimee, b.methode_valorisation = int(res["valeur"]), res["methode"]
                except Exception:
                    pass
                b.score_risque, _ = predictions.score_risque(b)
                b.save()
                crees += 1
            JournalAction.objects.create(organisation_id=profil.organisation_id, utilisateur=request.user, action="CREATION",
                                         objet_type="Import", objet_id="-", objet_libelle=f"Import de {crees} biens depuis {f.name}")
    return Response({
        "lignes": len(resultats), "valides": len(valides), "invalides": sum(1 for r in resultats if r["erreurs"]),
        "crees": crees, "colonnes_reconnues": sorted(set(correspondance.values())), "colonnes_ignorees": ignorees,
        "details": resultats[:500],
    })


@api_view(["GET"])
def modele_import(request):
    """Fichier Excel modèle, pré-rempli avec les districts et paroisses de l'organisation."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    profil = profil_de(request.user)
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventaire"
    entetes = ["Nom", "Catégorie", "Type précis", "District", "Paroisse", "État", "Statut juridique", "Surface m2",
               "Quantité", "Date acquisition", "Valeur", "Latitude", "Longitude", "Financeur", "Bénéficiaires", "Responsable", "Description"]
    ws.append(entetes)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1E6B47")
    d = District.objects.filter(organisation_id=profil.organisation_id).first()
    p = d.paroisses.first() if d else None
    ws.append(["Forage de la paroisse", "Infrastructure", "Forage", d.nom if d else "", p.nom if p else "", "Bon", "Non applicable",
               "", 1, "15/06/2024", 35000000, "", "", "UMCOR", 2000, "Pasteur responsable", "Exemple à remplacer"])
    for i, largeur in enumerate([30, 16, 18, 16, 18, 10, 18, 12, 10, 16, 14, 11, 11, 16, 13, 20, 30]):
        ws.column_dimensions[chr(65 + i)].width = largeur
    aide = wb.create_sheet("Valeurs possibles")
    aide.append(["Catégorie", "État", "Statut juridique", "District", "Paroisses"])
    cats = ["Foncier", "Immobilier", "Infrastructure", "Équipement", "Véhicule", "Agricole"]
    etats = ["Bon", "Moyen", "Mauvais", "En construction"]
    juri = ["Titre de propriété", "Démarches en cours", "Sans titre", "Non applicable"]
    dists = list(District.objects.filter(organisation_id=profil.organisation_id))
    for i in range(max(len(cats), len(dists))):
        dist = dists[i] if i < len(dists) else None
        aide.append([cats[i] if i < len(cats) else "", etats[i] if i < len(etats) else "", juri[i] if i < len(juri) else "",
                     dist.nom if dist else "", ", ".join(dist.paroisses.values_list("nom", flat=True)) if dist else ""])
    tampon = io.BytesIO()
    wb.save(tampon)
    rep = HttpResponse(tampon.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    rep["Content-Disposition"] = 'attachment; filename="umurage_modele_import.xlsx"'
    return rep


# ------------------------------------------------------------------ IATI

SECTEURS_DAC = {"SANTE": "12220", "EDUCATION": "11220", "EAU": "14030", "AGRICULTURE": "31120",
                "FEMMES": "15170", "HUMANITAIRE": "72010", "INCLUSION": "16010"}
STATUT_IATI = {"PREVU": "1", "EN_COURS": "2", "TERMINE": "4", "SUSPENDU": "6"}
PAYS_ISO = {"burundi": "BI", "rwanda": "RW", "kenya": "KE", "ouganda": "UG", "uganda": "UG", "tanzanie": "TZ", "tanzania": "TZ",
            "rdc": "CD", "republique democratique du congo": "CD", "congo": "CG", "ethiopie": "ET", "ethiopia": "ET",
            "soudan du sud": "SS", "south sudan": "SS", "mozambique": "MZ", "angola": "AO", "zimbabwe": "ZW", "zambie": "ZM",
            "zambia": "ZM", "nigeria": "NG", "cote d ivoire": "CI", "liberia": "LR", "sierra leone": "SL", "cameroun": "CM",
            "senegal": "SN", "maroc": "MA", "mauritanie": "MR", "malawi": "MW"}


@api_view(["GET"])
def export_iati(request):
    """Projets au format IATI 2.03 : les bailleurs peuvent intégrer ces données directement."""
    profil = profil_de(request.user)
    org = profil.organisation
    ref = f"XI-UMURAGE-{org.slug.upper()}"
    racine = ET.Element("iati-activities", {"version": "2.03", "generated-datetime": datetime.now().replace(microsecond=0).isoformat()})
    pays = PAYS_ISO.get(_norm(org.pays))
    for p in Projet.objects.filter(district__organisation=org).select_related("district"):
        a = ET.SubElement(racine, "iati-activity", {"default-currency": org.devise, "{http://www.w3.org/XML/1998/namespace}lang": org.langue})
        ET.SubElement(a, "iati-identifier").text = f"{ref}-{p.pk}"
        ro = ET.SubElement(a, "reporting-org", {"ref": ref, "type": "80"})
        ET.SubElement(ro, "narrative").text = org.nom
        ET.SubElement(ET.SubElement(a, "title"), "narrative").text = p.nom
        ET.SubElement(ET.SubElement(a, "description", {"type": "1"}), "narrative").text = p.description or p.nom
        po = ET.SubElement(a, "participating-org", {"role": "4", "type": "80"})
        ET.SubElement(po, "narrative").text = org.nom
        if p.financeur:
            pf = ET.SubElement(a, "participating-org", {"role": "1"})
            ET.SubElement(pf, "narrative").text = p.financeur
        ET.SubElement(a, "activity-status", {"code": STATUT_IATI.get(p.statut, "2")})
        if p.date_debut:
            ET.SubElement(a, "activity-date", {"type": "1", "iso-date": p.date_debut.isoformat()})
        if p.date_fin_prevue:
            ET.SubElement(a, "activity-date", {"type": "3", "iso-date": p.date_fin_prevue.isoformat()})
        if pays:
            ET.SubElement(a, "recipient-country", {"code": pays, "percentage": "100"})
        if p.latitude is not None:
            loc = ET.SubElement(a, "location")
            ET.SubElement(ET.SubElement(loc, "name"), "narrative").text = p.district.nom
            ET.SubElement(ET.SubElement(loc, "point", {"srsName": "http://www.opengis.net/def/crs/EPSG/0/4326"}), "pos").text = f"{p.latitude} {p.longitude}"
        ET.SubElement(a, "sector", {"vocabulary": "1", "code": SECTEURS_DAC.get(p.domaine, "43010"), "percentage": "100"})
        for odd in [o.strip() for o in p.odd.split(",") if o.strip()]:
            ET.SubElement(a, "tag", {"vocabulary": "2", "code": odd})
        if p.budget:
            b = ET.SubElement(a, "budget", {"type": "1", "status": "1"})
            ET.SubElement(b, "period-start", {"iso-date": (p.date_debut or date.today()).isoformat()})
            ET.SubElement(b, "period-end", {"iso-date": (p.date_fin_prevue or date.today()).isoformat()})
            ET.SubElement(b, "value", {"value-date": (p.date_debut or date.today()).isoformat()}).text = f"{float(p.budget):.0f}"
    ET.indent(racine)
    xml = ET.tostring(racine, encoding="utf-8", xml_declaration=True)
    rep = HttpResponse(xml, content_type="application/xml; charset=utf-8")
    rep["Content-Disposition"] = f'attachment; filename="iati_{org.slug}.xml"'
    return rep


# ------------------------------------------------------------------ Export comptable

@api_view(["GET"])
def export_transactions(request):
    profil = profil_de(request.user)
    if profil.role not in (R.ADMIN, R.TRESORIER, R.EVEQUE):
        raise PermissionDenied("Export réservé à la direction et au trésorier.")
    qs = Transaction.objects.filter(district__organisation_id=profil.organisation_id).select_related("district", "projet").order_by("date")
    for champ in ("sens", "categorie", "district"):
        if request.query_params.get(champ):
            qs = qs.filter(**{champ: request.query_params[champ]})
    rep = HttpResponse(content_type="text/csv; charset=utf-8")
    rep["Content-Disposition"] = 'attachment; filename="umurage_transactions.csv"'
    rep.write("﻿")
    w = csv.writer(rep, delimiter=";")
    dev = profil.organisation.devise
    w.writerow(["Date", "Sens", "Catégorie", "District", "Projet", "Tiers", "Description", "Canal", "Référence",
                "Montant", "Devise", f"Montant en {dev}", "Signalée par l'IA", "Vérifiée", "Motifs"])
    for t in qs:
        w.writerow([t.date, t.get_sens_display(), t.get_categorie_display(), t.district.nom, t.projet.nom if t.projet else "",
                    t.tiers, t.description, t.get_canal_display(), t.reference_externe, t.montant, t.devise, t.montant_bif,
                    "oui" if t.est_anomalie else "non", "oui" if t.verifiee else "non", " | ".join(t.motifs_anomalie)])
    return rep


# ------------------------------------------------------------------ Qualité des données

CRITERES = [
    ("gps", "Position GPS"),
    ("valeur", "Valeur d'acquisition"),
    ("date", "Date d'acquisition"),
    ("responsable", "Responsable désigné"),
    ("photo", "Photo"),
    ("titre", "Titre foncier (terrains)"),
    ("entretien", "Entretien de moins d'un an"),
]


def _criteres(b, derniere):
    c = {
        "gps": b.latitude is not None,
        "valeur": bool(b.valeur_acquisition),
        "date": b.date_acquisition is not None,
        "responsable": bool(b.responsable.strip()),
        "photo": bool(b.photo),
    }
    if b.categorie == "FON":
        c["titre"] = b.statut_juridique == "TITRE"
    elif b.etat != "CONSTRUCTION":
        c["entretien"] = derniere is not None and derniere >= date.today() - timedelta(days=365)
    return c


@api_view(["GET"])
def qualite(request):
    """Score de complétude par district (classement) et liste des biens à compléter."""
    profil = profil_de(request.user)
    district = "tout" if profil.voit_tout else profil.district_id
    return Response(cache_donnees.en_cache("qualite", profil.organisation_id, district, date.today(), calcul=lambda: _qualite(profil)))


def _qualite(profil):
    biens = Bien.objects.filter(district__organisation_id=profil.organisation_id).select_related("district")
    if not profil.voit_tout:
        biens = biens.filter(district_id=profil.district_id)
    derniers = dict(Mouvement.objects.filter(bien__in=biens, type__in=["MAINTENANCE", "REPARATION", "INSPECTION"])
                    .values("bien").annotate(d=Max("date")).values_list("bien", "d"))
    il_y_a_30j = date.today() - timedelta(days=30)
    par_district, a_completer = {}, []
    totaux = {k: [0, 0] for k, _ in CRITERES}
    for b in biens:
        c = _criteres(b, derniers.get(b.pk))
        score = round(100 * sum(c.values()) / len(c))
        d = par_district.setdefault(b.district_id, {"district": b.district.nom, "biens": 0, "somme": 0,
                                                    "criteres": {k: [0, 0] for k, _ in CRITERES}})
        d["biens"] += 1
        d["somme"] += score
        for k, ok in c.items():
            d["criteres"][k][0] += ok
            d["criteres"][k][1] += 1
            totaux[k][0] += ok
            totaux[k][1] += 1
        if score < 75:
            manque = [lib for k, lib in CRITERES if k in c and not c[k]]
            a_completer.append({"id": b.pk, "code": b.code, "nom": b.nom, "district": b.district.nom, "score": score, "manque": manque})
    nb_decl = {}
    for dist_id in Declaration.objects.filter(organisation_id=profil.organisation_id, recue_le__date__gte=il_y_a_30j).values_list("district", flat=True):
        nb_decl[dist_id] = nb_decl.get(dist_id, 0) + 1
    classement = []
    for dist_id, d in par_district.items():
        classement.append({
            "district": d["district"], "biens": d["biens"], "score": round(d["somme"] / d["biens"]),
            "declarations_30j": nb_decl.get(dist_id, 0),
            "criteres": {k: round(100 * v[0] / v[1]) if v[1] else None for k, v in d["criteres"].items()},
        })
    classement.sort(key=lambda x: (-x["score"], x["district"]))
    for i, c in enumerate(classement, 1):
        c["rang"] = i
    global_score = round(sum(c["score"] * c["biens"] for c in classement) / max(1, sum(c["biens"] for c in classement)))
    return {
        "score_global": global_score,
        "criteres": [{"id": k, "libelle": lib, "taux": round(100 * totaux[k][0] / totaux[k][1]) if totaux[k][1] else None} for k, lib in CRITERES],
        "classement": classement,
        "a_completer": sorted(a_completer, key=lambda x: x["score"])[:25],
    }
