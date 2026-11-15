"""
Comptabilité du patrimoine : registre des immobilisations, suivi budgétaire, clôture, rapprochement.

Amortissement linéaire, au prorata du nombre de mois de détention. Les terrains ne s'amortissent pas.
Les durées par défaut ci-dessous s'appliquent quand la fiche du bien n'indique pas de durée de vie ;
elles doivent être validées par l'expert-comptable de l'organisation.
"""
import csv
import io
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q, Sum

from finances.models import Transaction
from patrimoine.models import Bien

from .models import Budget

DUREES_DEFAUT = {"IMM": 40, "INF": 25, "EQP": 5, "VEH": 5, "AGR": 10}


def _mois_entre(debut, fin):
    """Nombre de mois entamés entre deux dates (au moins 0)."""
    if fin < debut:
        return 0
    return (fin.year - debut.year) * 12 + fin.month - debut.month + 1


def ligne_registre(b, annee):
    base = Decimal(b.valeur_acquisition or 0)
    debut_ex, fin_ex = date(annee, 1, 1), date(annee, 12, 31)
    fin_detention = min(fin_ex, b.date_sortie) if b.date_sortie else fin_ex
    amortissable = b.categorie != "FON" and base > 0 and b.date_acquisition is not None
    duree = b.duree_vie_ans or DUREES_DEFAUT.get(b.categorie)
    dotation = cumul = Decimal(0)
    if amortissable and duree and b.date_acquisition <= fin_detention:
        mensuel = base / (duree * 12)
        total_mois = duree * 12
        mois_avant = min(total_mois, _mois_entre(b.date_acquisition, debut_ex - timedelta(days=1)))
        mois_fin = min(total_mois, _mois_entre(b.date_acquisition, fin_detention))
        dotation = mensuel * (mois_fin - mois_avant)
        cumul = mensuel * mois_fin
    return {
        "id": b.pk, "code": b.code, "nom": b.nom, "categorie": b.categorie, "district": b.district.nom,
        "date_acquisition": b.date_acquisition.isoformat() if b.date_acquisition else None,
        "valeur_origine": float(base), "duree_ans": duree if amortissable else None,
        "dotation_exercice": round(float(dotation)), "amortissements_cumules": round(float(cumul)),
        "valeur_nette_comptable": round(float(base - cumul)),
        "sorti_le": b.date_sortie.isoformat() if b.date_sortie else None,
        "amortissable": amortissable,
    }


def registre(biens, annee):
    # Biens détenus pendant l'exercice : acquis avant la fin d'année et non sortis avant son début
    biens = biens.filter(Q(date_acquisition__lte=date(annee, 12, 31)) | Q(date_acquisition__isnull=True))
    biens = biens.filter(Q(date_sortie__isnull=True) | Q(date_sortie__gte=date(annee, 1, 1))).select_related("district")
    lignes = [ligne_registre(b, annee) for b in biens.order_by("code")]
    totaux = {k: sum(l[k] for l in lignes) for k in ("valeur_origine", "dotation_exercice", "amortissements_cumules", "valeur_nette_comptable")}
    return {"annee": annee, "lignes": lignes, "totaux": totaux,
            "non_amortissables": sum(1 for l in lignes if not l["amortissable"])}


def registre_csv(donnees):
    sortie = io.StringIO()
    w = csv.writer(sortie, delimiter=";")
    w.writerow(["Code", "Bien", "Catégorie", "District", "Date d'acquisition", "Valeur d'origine", "Durée (ans)",
                f"Dotation {donnees['annee']}", "Amortissements cumulés", "Valeur nette comptable", "Sorti le"])
    for l in donnees["lignes"]:
        w.writerow([l["code"], l["nom"], l["categorie"], l["district"], l["date_acquisition"] or "", round(l["valeur_origine"]),
                    l["duree_ans"] or "", l["dotation_exercice"], l["amortissements_cumules"], l["valeur_nette_comptable"], l["sorti_le"] or ""])
    t = donnees["totaux"]
    w.writerow(["TOTAL", "", "", "", "", round(t["valeur_origine"]), "", t["dotation_exercice"], t["amortissements_cumules"], t["valeur_nette_comptable"], ""])
    return "﻿" + sortie.getvalue()


def suivi_budget(organisation_id, annee, district_id=None):
    """Budget comparé au réalisé, ligne par ligne, avec les dépenses non budgétées."""
    trans = Transaction.objects.filter(district__organisation_id=organisation_id, date__year=annee)
    budgets = Budget.objects.filter(organisation_id=organisation_id, annee=annee)
    if district_id:
        trans = trans.filter(district_id=district_id)
        budgets = budgets.filter(Q(district_id=district_id) | Q(district__isnull=True))
    libelles = dict(Transaction.Categorie.choices)
    lignes, couverts = [], set()
    for b in budgets.select_related("district", "projet"):
        qs = trans.filter(sens=b.sens, categorie=b.categorie)
        if b.district_id:
            qs = qs.filter(district_id=b.district_id)
        if b.projet_id:
            qs = qs.filter(projet_id=b.projet_id)
        realise = float(qs.aggregate(s=Sum("montant_bif"))["s"] or 0)
        couverts.add((b.sens, b.categorie))
        prevu = float(b.montant)
        lignes.append({
            "id": b.pk, "sens": b.sens, "categorie": b.categorie, "categorie_libelle": libelles.get(b.categorie, b.categorie),
            "district": b.district.nom if b.district else "Toute l'organisation", "projet": b.projet.nom if b.projet else None,
            "prevu": prevu, "realise": realise, "ecart": realise - prevu,
            "taux": round(100 * realise / prevu) if prevu else None,
            "alerte": b.sens == "DEPENSE" and prevu > 0 and realise > prevu,
        })
    hors_budget = [
        {"sens": l["sens"], "categorie": l["categorie"], "categorie_libelle": libelles.get(l["categorie"], l["categorie"]), "realise": float(l["t"])}
        for l in trans.values("sens", "categorie").annotate(t=Sum("montant_bif")).order_by("-t")
        if (l["sens"], l["categorie"]) not in couverts
    ]
    seuil = Decimal(500000)
    sans_piece = (trans.filter(sens="DEPENSE", montant_bif__gte=seuil).annotate(n=Count("pieces")).filter(n=0))
    return {
        "annee": annee, "lignes": lignes, "hors_budget": hors_budget,
        "total_prevu_depenses": sum(l["prevu"] for l in lignes if l["sens"] == "DEPENSE"),
        "total_realise_depenses": float(trans.filter(sens="DEPENSE").aggregate(s=Sum("montant_bif"))["s"] or 0),
        "total_prevu_recettes": sum(l["prevu"] for l in lignes if l["sens"] == "RECETTE"),
        "total_realise_recettes": float(trans.filter(sens="RECETTE").aggregate(s=Sum("montant_bif"))["s"] or 0),
        "depenses_sans_piece": {"seuil": float(seuil), "nombre": sans_piece.count(),
                                "exemples": list(sans_piece.order_by("-montant_bif").values("id", "date", "tiers", "description", "montant_bif")[:10])},
        "non_rapprochees": trans.filter(rapprochee=False).exclude(canal="ESPECES").count(),
    }


def totaux_exercice(organisation_id, annee):
    t = Transaction.objects.filter(district__organisation_id=organisation_id, date__year=annee)
    return {
        "recettes": float(t.filter(sens="RECETTE").aggregate(s=Sum("montant_bif"))["s"] or 0),
        "depenses": float(t.filter(sens="DEPENSE").aggregate(s=Sum("montant_bif"))["s"] or 0),
        "transactions": t.count(),
        "valeur_nette_comptable": registre(Bien.objects.filter(district__organisation_id=organisation_id), annee)["totaux"]["valeur_nette_comptable"],
    }


def _nombre(texte):
    t = str(texte or "").replace(" ", "").replace(" ", "").replace("\xa0", "")
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    try:
        return abs(Decimal(t))
    except InvalidOperation:
        return None


def _date(texte):
    from datetime import datetime
    for f in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(str(texte).strip(), f).date()
        except ValueError:
            continue
    return None


def rapprocher(organisation_id, fichier_texte, tolerance_jours=3):
    """
    Rapprochement avec un relevé bancaire ou Mobile Money (CSV : date ; montant ; référence ; libellé).
    Une ligne correspond à une transaction de même référence, ou de même montant à quelques jours près.
    """
    echantillon = fichier_texte[:2000]
    sep = ";" if echantillon.count(";") >= echantillon.count(",") else ","
    lecteur = csv.DictReader(io.StringIO(fichier_texte.lstrip("﻿")), delimiter=sep)
    cles = {k.lower().strip(): k for k in (lecteur.fieldnames or [])}
    col = lambda *noms: next((cles[n] for n in noms if n in cles), None)
    c_date, c_montant = col("date", "date operation", "date opération"), col("montant", "amount", "credit", "crédit", "debit", "débit")
    c_ref, c_lib = col("reference", "référence", "ref", "transaction id"), col("libelle", "libellé", "description")
    if not (c_date and c_montant):
        return {"erreur": "Colonnes « date » et « montant » introuvables dans le relevé."}
    base = Transaction.objects.filter(district__organisation_id=organisation_id, rapprochee=False)
    trouves, orphelins = [], []
    for ligne in lecteur:
        d, m = _date(ligne.get(c_date)), _nombre(ligne.get(c_montant))
        ref = (ligne.get(c_ref) or "").strip() if c_ref else ""
        if d is None or m is None:
            continue
        t = base.filter(reference_externe=ref).first() if ref else None
        if t is None:
            t = (base.filter(montant=m, date__range=(d - timedelta(days=tolerance_jours), d + timedelta(days=tolerance_jours)))
                 .order_by("date").first())
        if t:
            t.rapprochee = True
            t.save(update_fields=["rapprochee"])
            base = base.exclude(pk=t.pk)
            trouves.append({"ligne": {"date": d.isoformat(), "montant": float(m), "reference": ref}, "transaction": t.pk})
        else:
            orphelins.append({"date": d.isoformat(), "montant": float(m), "reference": ref, "libelle": ligne.get(c_lib, "") if c_lib else ""})
    return {"rapprochees": len(trouves), "lignes_sans_correspondance": orphelins, "details": trouves}
