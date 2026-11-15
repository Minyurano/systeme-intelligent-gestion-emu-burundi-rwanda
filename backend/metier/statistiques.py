"""
Statistiques de l'Église : une seule réponse qui rassemble les chiffres clés pour un tableau de bord lisible.

- Membres : effectifs, croissance sur 12 mois, statuts, sexe, tranches d'âge, ministères.
- Comparaison année en cours / année précédente, à la même date (comparaison équitable).
- Comparaison des districts sur les mêmes indicateurs.
- Patrimoine et finances : catégories, états, recettes et dépenses mensuelles.
- Travail en attente : approbations, échéances, travaux, loyers.
Tout reste cloisonné à l'organisation, et au district pour un surintendant ou un agent.
"""
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth

from core.models import District, Paroisse
from finances.models import Transaction
from patrimoine.models import Bien, Declaration

from .models import Demande, Echeance, Loyer, MembreEglise, OrdreTravail, ajouter_mois

VALEUR = Coalesce("valeur_estimee", "valeur_acquisition")
TRANCHES = [("0-12 ans", 0, 12), ("13-17 ans", 13, 17), ("18-35 ans", 18, 35), ("36-59 ans", 36, 59), ("60 ans et +", 60, 200)]


def _f(v):
    return float(v or 0)


def _evolution(actuel, precedent):
    if not precedent:
        return None
    return round(100 * (actuel - precedent) / precedent, 1)


def statistiques(profil, district_id=None):
    org = profil.organisation_id
    if not profil.voit_tout:
        district_id = profil.district_id
    j = date.today()
    debut_annee, debut_annee_prec = j.replace(month=1, day=1), j.replace(year=j.year - 1, month=1, day=1)
    meme_jour_prec = j.replace(year=j.year - 1) if not (j.month == 2 and j.day == 29) else j.replace(year=j.year - 1, day=28)

    districts = District.objects.filter(organisation_id=org)
    membres = MembreEglise.objects.filter(paroisse__district__organisation_id=org)
    paroisses = Paroisse.objects.filter(district__organisation_id=org)
    biens = Bien.objects.filter(district__organisation_id=org, date_sortie__isnull=True)
    trans = Transaction.objects.filter(district__organisation_id=org)
    if district_id:
        districts = districts.filter(pk=district_id)
        membres = membres.filter(paroisse__district_id=district_id)
        paroisses = paroisses.filter(district_id=district_id)
        biens = biens.filter(district_id=district_id)
        trans = trans.filter(district_id=district_id)
    actifs = membres.filter(statut__in=MembreEglise.ACTIFS)
    declares = paroisses.aggregate(n=Sum("membres"))["n"] or 0

    # ---------------------------------------------------------------- Membres
    debut_12 = ajouter_mois(j.replace(day=1), -11)
    nouveaux = dict(membres.filter(date_adhesion__gte=debut_12).annotate(m=TruncMonth("date_adhesion"))
                    .values_list("m").annotate(n=Count("id")).values_list("m", "n"))
    avant = actifs.filter(date_adhesion__lt=debut_12).count()
    croissance, cumul, m = [], avant, debut_12
    nouveaux = {(k.year, k.month): v for k, v in nouveaux.items()}
    for _ in range(12):
        n = nouveaux.get((m.year, m.month), 0)
        cumul += n
        croissance.append({"mois": m.isoformat(), "nouveaux": n, "total": cumul})
        m = ajouter_mois(m, 1)

    statuts = dict(membres.values_list("statut").annotate(n=Count("id")))
    par_statut = [{"cle": k, "libelle": l, "n": statuts.get(k, 0)} for k, l in MembreEglise.Statut.choices]
    sexe = dict(actifs.values_list("sexe").annotate(n=Count("id")))

    ages = {t[0]: {"tranche": t[0], "femmes": 0, "hommes": 0} for t in TRANCHES}
    sans_age = 0
    for naissance, s in actifs.values_list("date_naissance", "sexe"):
        if not naissance:
            sans_age += 1
            continue
        age = j.year - naissance.year - ((j.month, j.day) < (naissance.month, naissance.day))
        for nom, a, b in TRANCHES:
            if a <= age <= b:
                ages[nom]["femmes" if s == "F" else "hommes"] += 1
                break
    ministeres = list(actifs.exclude(ministere="").values("ministere").annotate(n=Count("id")).order_by("-n", "ministere")[:7])

    # ---------------------------------------------------------------- Année en cours / année précédente (même date)
    def periode(qs, champ, debut, fin):
        return qs.filter(**{f"{champ}__gte": debut, f"{champ}__lte": fin})

    def somme(qs):
        return _f(qs.aggregate(s=Sum("montant_bif"))["s"])

    ord_ = OrdreTravail.objects.filter(bien__district__organisation_id=org, statut="TERMINE")
    decl = Declaration.objects.filter(organisation_id=org)
    if district_id:
        ord_ = ord_.filter(bien__district_id=district_id)
        decl = decl.filter(district_id=district_id)
    rec, dep = trans.filter(sens="RECETTE"), trans.filter(sens="DEPENSE")
    indicateurs = [
        ("Nouveaux membres", "membres", lambda a, b: periode(membres, "date_adhesion", a, b).count(), "", 1),
        ("Baptêmes", "baptemes", lambda a, b: periode(membres, "date_bapteme", a, b).count(), "", 1),
        ("Recettes", "recettes", lambda a, b: somme(periode(rec, "date", a, b)), "monnaie", 1),
        ("Dîmes et offrandes", "dimes", lambda a, b: somme(periode(rec.filter(categorie="DIME"), "date", a, b)), "monnaie", 1),
        ("Dépenses", "depenses", lambda a, b: somme(periode(dep, "date", a, b)), "monnaie", -1),
        ("Biens acquis", "biens", lambda a, b: periode(biens, "date_acquisition", a, b).count(), "", 1),
        ("Travaux terminés", "travaux", lambda a, b: periode(ord_, "termine_le", a, b).count(), "", 1),
        ("Déclarations du terrain", "declarations", lambda a, b: periode(decl, "recue_le__date", a, b).count(), "", 1),
    ]
    annee = []
    for libelle, cle, calcul, unite, sens in indicateurs:
        a, p = calcul(debut_annee, j), calcul(debut_annee_prec, meme_jour_prec)
        annee.append({"cle": cle, "libelle": libelle, "actuel": a, "precedent": p, "evolution": _evolution(a, p), "ecart": a - p, "unite": unite, "sens": sens})
    solde_a = next(x["actuel"] for x in annee if x["cle"] == "recettes") - next(x["actuel"] for x in annee if x["cle"] == "depenses")
    solde_p = next(x["precedent"] for x in annee if x["cle"] == "recettes") - next(x["precedent"] for x in annee if x["cle"] == "depenses")
    annee.insert(5, {"cle": "solde", "libelle": "Solde (recettes - dépenses)", "actuel": solde_a, "precedent": solde_p,
                     "evolution": None, "ecart": solde_a - solde_p, "unite": "monnaie", "sens": 1})

    # ---------------------------------------------------------------- Finances sur 12 mois
    mois_fin = {(k.year, k.month): v for k, *v in trans.filter(date__gte=debut_12).annotate(m=TruncMonth("date")).values("m")
                .annotate(r=Sum("montant_bif", filter=Q(sens="RECETTE")), d=Sum("montant_bif", filter=Q(sens="DEPENSE")),
                          di=Sum("montant_bif", filter=Q(sens="RECETTE", categorie="DIME")),
                          lo=Sum("montant_bif", filter=Q(sens="RECETTE", categorie="LOYER")))
                .values_list("m", "r", "d", "di", "lo")}
    finances, m = [], debut_12
    for _ in range(12):
        r, d, di, lo = mois_fin.get((m.year, m.month), (0, 0, 0, 0))
        n = nouveaux.get((m.year, m.month), 0)
        finances.append({"mois": m.isoformat(), "recettes": _f(r), "depenses": _f(d), "solde": _f(r) - _f(d), "dimes": _f(di),
                         "loyers": _f(lo), "nouveaux_membres": n})
        m = ajouter_mois(m, 1)

    # ---------------------------------------------------------------- Répartition des recettes et dépenses (année en cours)
    libelles_cat = dict(Transaction.Categorie.choices)
    repartition = {}
    for sens, cle in (("RECETTE", "recettes"), ("DEPENSE", "depenses")):
        lignes = list(trans.filter(sens=sens, date__gte=debut_annee).values("categorie").annotate(s=Sum("montant_bif"), n=Count("id")).order_by("-s"))
        total = sum(_f(x["s"]) for x in lignes) or 1
        repartition[cle] = [{"cle": x["categorie"], "libelle": libelles_cat.get(x["categorie"], x["categorie"]), "montant": _f(x["s"]),
                             "operations": x["n"], "part": round(100 * _f(x["s"]) / total, 1)} for x in lignes]

    # ---------------------------------------------------------------- Projections de fin d'année, au rythme actuel
    jour_annee = (j - debut_annee).days + 1
    jours_total = (date(j.year + 1, 1, 1) - debut_annee).days
    an_prec_complet = lambda calcul: calcul(debut_annee_prec, date(j.year - 1, 12, 31))  # noqa: E731
    projections = []
    for libelle, cle, calcul, unite, sens in indicateurs:
        if cle not in ("membres", "baptemes", "recettes", "dimes", "depenses"):
            continue
        a = calcul(debut_annee, j)
        projections.append({"cle": cle, "libelle": libelle, "unite": unite, "sens": sens, "a_date": a,
                            "projection": round(a * jours_total / jour_annee, 0), "annee_precedente": an_prec_complet(calcul)})
    avancement_annee = round(100 * jour_annee / jours_total, 1)

    # ---------------------------------------------------------------- Comparaison des districts
    inscrits_d = dict(actifs.values_list("paroisse__district").annotate(n=Count("id")))
    decl_d = dict(paroisses.values_list("district").annotate(n=Sum("membres")))
    eglises_d = dict(paroisses.values_list("district").annotate(n=Count("id")))
    biens_d = {x["district"]: x for x in biens.values("district").annotate(n=Count("id"), v=Sum(VALEUR))}
    fin_d = {x["district"]: x for x in trans.filter(date__gte=debut_annee).values("district").annotate(
        r=Sum("montant_bif", filter=Q(sens="RECETTE")), d=Sum("montant_bif", filter=Q(sens="DEPENSE")),
        dime=Sum("montant_bif", filter=Q(sens="RECETTE", categorie="DIME")))}
    comp = []
    for d in districts.order_by("nom"):
        dec, ins = decl_d.get(d.pk) or 0, inscrits_d.get(d.pk, 0)
        b, f = biens_d.get(d.pk, {}), fin_d.get(d.pk, {})
        comp.append({
            "id": d.pk, "nom": d.nom, "code": d.code, "eglises": eglises_d.get(d.pk, 0),
            "membres_declares": dec, "membres_inscrits": ins, "taux_enregistrement": round(100 * ins / dec, 2) if dec else None,
            "biens": b.get("n", 0), "valeur": _f(b.get("v")), "recettes": _f(f.get("r")), "depenses": _f(f.get("d")),
            "solde": _f(f.get("r")) - _f(f.get("d")), "dimes_par_membre": round(_f(f.get("dime")) / dec) if dec else None,
        })

    # ---------------------------------------------------------------- Églises locales : matrice à mise en forme conditionnelle
    m_par = {x["paroisse"]: x for x in membres.values("paroisse").annotate(
        actifs=Count("id", filter=Q(statut__in=MembreEglise.ACTIFS)),
        baptises=Count("id", filter=Q(statut__in=["BAPTISE", "CONFESSANT"])),
        femmes=Count("id", filter=Q(statut__in=MembreEglise.ACTIFS, sexe="F")),
        nouveaux=Count("id", filter=Q(date_adhesion__gte=j - timedelta(days=365))))}
    b_par = {x["paroisse"]: x for x in biens.filter(paroisse__isnull=False).values("paroisse").annotate(
        n=Count("id"), risque=Count("id", filter=Q(score_risque__gte=50)), v=Sum(VALEUR))}
    eglises = []
    for p in paroisses.select_related("district").order_by("district__nom", "nom"):
        a, b = m_par.get(p.pk, {}), b_par.get(p.pk, {})
        act = a.get("actifs", 0)
        eglises.append({
            "id": p.pk, "nom": p.nom, "district": p.district.nom, "pasteur": p.pasteur, "declares": p.membres, "inscrits": act,
            "taux": round(100 * act / p.membres, 2) if p.membres else None,
            "pct_baptises": round(100 * a.get("baptises", 0) / act) if act else None,
            "pct_femmes": round(100 * a.get("femmes", 0) / act) if act else None,
            "nouveaux_12m": a.get("nouveaux", 0), "biens": b.get("n", 0), "biens_risque": b.get("risque", 0), "valeur": _f(b.get("v")),
        })

    # ---------------------------------------------------------------- Patrimoine
    cats = {x["categorie"]: x for x in biens.values("categorie").annotate(n=Count("id"), v=Sum(VALEUR))}
    patrimoine = [{"cle": k, "libelle": l.split(" (")[0], "n": cats.get(k, {}).get("n", 0), "valeur": _f(cats.get(k, {}).get("v"))}
                  for k, l in Bien.Categorie.choices]
    etats = dict(biens.values_list("etat").annotate(n=Count("id")))

    # ---------------------------------------------------------------- Travail en attente
    ech = Echeance.objects.filter(organisation_id=org, statut="A_FAIRE", date__lte=j + timedelta(days=30))
    ot = OrdreTravail.objects.filter(bien__district__organisation_id=org, statut__in=OrdreTravail.OUVERTS)
    loy = Loyer.objects.filter(bail__bien__district__organisation_id=org, echeance__lt=j)
    dem = Demande.objects.filter(organisation_id=org, statut__in=["EN_ATTENTE", "APPROUVEE"])
    if district_id:
        ech = ech.filter(Q(district_id=district_id) | Q(district__isnull=True))
        ot, loy, dem = ot.filter(bien__district_id=district_id), loy.filter(bail__bien__district_id=district_id), dem.filter(district_id=district_id)
    impayes = [l for l in loy if l.reste > 0]
    a_traiter = {
        "demandes": dem.count(), "echeances_30j": ech.count(), "echeances_retard": ech.filter(date__lt=j).count(),
        "travaux": ot.count(), "travaux_urgents": ot.filter(priorite="URGENTE").count(),
        "loyers_impayes": len(impayes), "montant_impayes": sum(_f(l.reste) for l in impayes),
    }
    a_traiter["total"] = a_traiter["demandes"] + a_traiter["echeances_30j"] + a_traiter["travaux"] + a_traiter["loyers_impayes"]

    return {
        "date": j.isoformat(), "annee": j.year, "district": district_id,
        "membres": {
            "inscrits": membres.count(), "actifs": actifs.count(), "declares": declares,
            "taux_enregistrement": round(100 * actifs.count() / declares, 2) if declares else None,
            "femmes": sexe.get("F", 0), "hommes": sexe.get("H", 0),
            "baptises": actifs.filter(statut__in=["BAPTISE", "CONFESSANT"]).count(),
            "croissance": croissance, "par_statut": par_statut, "ages": list(ages.values()), "sans_age": sans_age,
            "ministeres": ministeres, "eglises": paroisses.count(),
        },
        "annee_comparee": annee, "finances": finances, "districts": comp, "repartition": repartition, "eglises": eglises,
        "projections": projections, "avancement_annee": avancement_annee,
        "patrimoine": {"categories": patrimoine, "total": sum(c["n"] for c in patrimoine), "valeur": sum(c["valeur"] for c in patrimoine),
                       "etats": [{"cle": k, "libelle": l, "n": etats.get(k, 0)} for k, l in Bien.Etat.choices]},
        "a_traiter": a_traiter,
    }
