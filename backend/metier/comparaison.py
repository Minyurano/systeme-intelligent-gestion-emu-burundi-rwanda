"""
Comparaison des églises locales (paroisses) et des districts d'une organisation.

Chaque entité reçoit les mêmes indicateurs, calculés sur l'exercice en cours, et un indice de bonne gestion
(moyenne de quatre taux sur 100) pour un classement lisible. La comparaison reste à l'intérieur d'une organisation :
les données d'une autre Église ne sont jamais exposées.
"""
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Count, Max, Q, Sum
from django.db.models.functions import Coalesce

from core.models import District, Paroisse
from finances.models import Transaction
from patrimoine.models import Bien, Declaration, Mouvement
from patrimoine.outils import _criteres

from .models import Contribution, Loyer, MembreEglise, OrdreTravail

VALEUR = Coalesce("valeur_estimee", "valeur_acquisition")

INDICATEURS = [
    # (clé, libellé, unité, sens : 1 = plus c'est haut mieux c'est, -1 = l'inverse, 0 = neutre)
    ("indice", "Indice de bonne gestion", "/100", 1),
    ("biens", "Biens recensés", "", 0),
    ("valeur", "Valeur du patrimoine", "monnaie", 0),
    ("valeur_par_membre", "Patrimoine par membre", "monnaie", 0),
    ("qualite", "Complétude des fiches", "%", 1),
    ("pct_titres", "Terrains titrés", "%", 1),
    ("pct_a_risque", "Biens à risque élevé", "%", -1),
    ("mauvais", "Biens en mauvais état", "", -1),
    ("ordres_ouverts", "Travaux en attente", "", -1),
    ("loyers_encaisses", "Loyers encaissés (année)", "monnaie", 1),
    ("taux_recouvrement", "Recouvrement des loyers", "%", 1),
    ("beneficiaires", "Bénéficiaires des infrastructures", "", 1),
    ("dons_par_membre", "Dîmes et offrandes par membre (année)", "monnaie", 1),
    ("taux_registre", "Membres inscrits au registre", "%", 1),
]
INDICATEURS_DISTRICT = INDICATEURS + [
    ("recettes", "Recettes (année)", "monnaie", 1),
    ("depenses", "Dépenses (année)", "monnaie", 0),
    ("solde", "Solde (année)", "monnaie", 1),
    ("dimes_par_membre", "Dîmes par membre (année)", "monnaie", 1),
    ("declarations_30j", "Déclarations WhatsApp (30 j)", "", 1),
]


def _pct(a, b):
    return round(100 * a / b) if b else None


def _indice(l):
    """Moyenne des taux disponibles : complétude, titres, biens hors risque, recouvrement des loyers."""
    taux = [l["qualite"], l["pct_titres"], 100 - l["pct_a_risque"] if l["pct_a_risque"] is not None else None, l["taux_recouvrement"]]
    taux = [t for t in taux if t is not None]
    return round(sum(taux) / len(taux)) if taux else None


def comparer(organisation_id, niveau="paroisse", district_id=None, annee=None):
    annee = annee or date.today().year
    cle = "paroisse_id" if niveau == "paroisse" else "district_id"
    biens = Bien.objects.filter(district__organisation_id=organisation_id, date_sortie__isnull=True)
    if district_id:
        biens = biens.filter(district_id=district_id)
    if niveau == "paroisse":
        entites = Paroisse.objects.filter(district__organisation_id=organisation_id).select_related("district")
        if district_id:
            entites = entites.filter(district_id=district_id)
        biens = biens.filter(paroisse__isnull=False)
    else:
        entites = District.objects.filter(organisation_id=organisation_id).annotate(membres_total=Sum("paroisses__membres"))
        if district_id:
            entites = entites.filter(pk=district_id)

    agregats = {l[cle]: l for l in biens.values(cle).annotate(
        n=Count("id"), valeur=Sum(VALEUR), benef=Sum("beneficiaires"),
        terrains=Count("id", filter=Q(categorie="FON")), titres=Count("id", filter=Q(categorie="FON", statut_juridique="TITRE")),
        risque=Count("id", filter=Q(score_risque__gte=50)), mauvais=Count("id", filter=Q(etat="MAUVAIS")),
    )}

    # Complétude des fiches (mêmes critères que la page Qualité des données)
    derniers = dict(Mouvement.objects.filter(bien__in=biens, type__in=["MAINTENANCE", "REPARATION", "INSPECTION"])
                    .values("bien").annotate(d=Max("date")).values_list("bien", "d"))
    scores = defaultdict(list)
    for b in biens.only("id", "paroisse_id", "district_id", "latitude", "valeur_acquisition", "date_acquisition", "responsable",
                        "photo", "categorie", "statut_juridique", "etat"):
        c = _criteres(b, derniers.get(b.pk))
        scores[getattr(b, cle)].append(100 * sum(c.values()) / len(c))

    ordres = dict(OrdreTravail.objects.filter(bien__in=biens, statut__in=OrdreTravail.OUVERTS)
                  .values(f"bien__{cle}").annotate(n=Count("id")).values_list(f"bien__{cle}", "n"))
    loyers = {l[f"bail__bien__{cle}"]: l for l in Loyer.objects.filter(bail__bien__in=biens, periode__year=annee, echeance__lte=date.today())
              .values(f"bail__bien__{cle}").annotate(du=Sum("montant_du"), paye=Sum("montant_paye"))}

    # Dîmes et offrandes enregistrées (hors reçus annulés) et membres inscrits au registre, par entité
    cle_par = "paroisse_id" if niveau == "paroisse" else "paroisse__district_id"
    contribs = Contribution.objects.filter(organisation_id=organisation_id, annulee=False, date__year=annee)
    dons = dict(contribs.values(cle_par).annotate(s=Sum("montant")).values_list(cle_par, "s"))
    inscrits = dict(MembreEglise.objects.filter(paroisse__district__organisation_id=organisation_id, statut__in=MembreEglise.ACTIFS)
                    .values(cle_par).annotate(n=Count("id")).values_list(cle_par, "n"))

    finances = {}
    if niveau == "district":
        trans = Transaction.objects.filter(district__organisation_id=organisation_id, date__year=annee)
        finances = {l["district_id"]: l for l in trans.values("district_id").annotate(
            recettes=Sum("montant_bif", filter=Q(sens="RECETTE")), depenses=Sum("montant_bif", filter=Q(sens="DEPENSE")),
            dimes=Sum("montant_bif", filter=Q(sens="RECETTE", categorie="DIME")),
        )}
        decl = dict(Declaration.objects.filter(organisation_id=organisation_id, recue_le__date__gte=date.today() - timedelta(days=30))
                    .values("district_id").annotate(n=Count("id")).values_list("district_id", "n"))

    lignes = []
    for e in entites:
        a = agregats.get(e.pk, {})
        membres = e.membres if niveau == "paroisse" else (e.membres_total or 0)
        valeur = float(a.get("valeur") or 0)
        lo = loyers.get(e.pk, {})
        l = {
            "id": e.pk, "nom": e.nom, "district": e.district.nom if niveau == "paroisse" else None,
            "responsable": getattr(e, "pasteur", "") or "", "membres": membres,
            "biens": a.get("n", 0), "valeur": valeur, "valeur_par_membre": round(valeur / membres) if membres else None,
            "qualite": round(sum(scores[e.pk]) / len(scores[e.pk])) if scores.get(e.pk) else None,
            "terrains": a.get("terrains", 0), "pct_titres": _pct(a.get("titres", 0), a.get("terrains", 0)),
            "pct_a_risque": _pct(a.get("risque", 0), a.get("n", 0)), "mauvais": a.get("mauvais", 0),
            "ordres_ouverts": ordres.get(e.pk, 0),
            "loyers_encaisses": float(lo.get("paye") or 0), "taux_recouvrement": _pct(float(lo.get("paye") or 0), float(lo.get("du") or 0)),
            "beneficiaires": a.get("benef") or 0,
            "dons_par_membre": round(float(dons.get(e.pk) or 0) / membres) if membres else None,
            "taux_registre": min(100, _pct(inscrits.get(e.pk, 0), membres)) if membres else None,
        }
        if niveau == "district":
            f = finances.get(e.pk, {})
            l.update(recettes=float(f.get("recettes") or 0), depenses=float(f.get("depenses") or 0),
                     dimes_par_membre=round(float(f.get("dimes") or 0) / membres) if membres else None,
                     declarations_30j=decl.get(e.pk, 0))
            l["solde"] = l["recettes"] - l["depenses"]
        l["indice"] = _indice(l)
        lignes.append(l)

    lignes.sort(key=lambda x: (x["indice"] is None, -(x["indice"] or 0), x["nom"]))
    for rang, l in enumerate(lignes, 1):
        l["rang"] = rang
    indicateurs = INDICATEURS_DISTRICT if niveau == "district" else INDICATEURS
    moyennes = {}
    for k, *_ in indicateurs:
        vals = [l[k] for l in lignes if l.get(k) is not None]
        moyennes[k] = round(sum(vals) / len(vals), 1) if vals else None
    return {
        "niveau": niveau, "annee": annee,
        "indicateurs": [{"cle": k, "libelle": lib, "unite": u, "sens": s} for k, lib, u, s in indicateurs],
        "lignes": lignes, "moyennes": moyennes,
        "methode": "Indice de bonne gestion = moyenne de : complétude des fiches, part des terrains titrés, "
                   "part des biens hors risque élevé, taux de recouvrement des loyers (seuls les taux disponibles comptent).",
    }
