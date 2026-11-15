import csv
import io
from collections import defaultdict

import qrcode
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.models import District, Organisation, Profil
from core.securite import DistrictScopedMixin, JournalMixin, profil_de
from finances.models import Transaction
from ia import predictions, valorisation
from iot.models import Alerte

from . import cache_donnees
from .extraction import extraire_texte
from .models import ODD_LIBELLES, Bien, Declaration, Document, Mouvement, Projet
from .serializers import BienSerializer, DocumentSerializer, MouvementSerializer, ProjetSerializer

R = Profil.Role
ECRITURE_TERRAIN = (R.ADMIN, R.SURINTENDANT, R.AGENT)


class BienViewSet(DistrictScopedMixin, JournalMixin, viewsets.ModelViewSet):
    queryset = Bien.objects.select_related("district", "paroisse")
    serializer_class = BienSerializer
    roles_ecriture = ECRITURE_TERRAIN
    filterset_fields = {
        "district": ["exact"], "paroisse": ["exact"], "categorie": ["exact"], "etat": ["exact"],
        "statut_juridique": ["exact"], "score_risque": ["gte"],
    }
    search_fields = ["code", "nom", "sous_type", "description", "responsable", "financeur"]
    ordering_fields = ["code", "nom", "valeur_estimee", "score_risque", "date_acquisition"]

    def get_queryset(self):
        qs = super().get_queryset()
        # Les biens cédés restent consultables (fiche, historique) mais sortent de la liste, sauf demande expresse
        if self.action == "list" and self.request.query_params.get("sortis") != "1":
            qs = qs.filter(date_sortie__isnull=True)
        return qs

    def perform_create(self, serializer):
        super().perform_create(serializer)
        self._actualiser(serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        self._actualiser(serializer.instance)

    def _actualiser(self, bien):
        """Recalcule valeur et risque dès qu'un bien est créé ou modifié."""
        try:
            res = valorisation.estimer(bien)
            bien.valeur_estimee, bien.methode_valorisation = int(res["valeur"]), res["methode"]
        except Exception:
            pass
        bien.score_risque, _ = predictions.score_risque(bien)
        bien.save(update_fields=["valeur_estimee", "methode_valorisation", "score_risque"])

    @action(detail=True)
    def qrcode(self, request, pk=None):
        bien = self.get_object()
        url = f"{settings.UMURAGE['FRONTEND_URL']}/biens/{bien.pk}"
        img = qrcode.make(url, box_size=8, border=2)
        tampon = io.BytesIO()
        img.save(tampon, format="PNG")
        rep = HttpResponse(tampon.getvalue(), content_type="image/png")
        rep["Content-Disposition"] = f'inline; filename="{bien.code}.png"'
        return rep

    @action(detail=True)
    def analyse(self, request, pk=None):
        """Valorisation expliquée et score de risque d'un bien."""
        bien = self.get_object()
        try:
            val = valorisation.estimer(bien)
        except Exception as e:
            val = {"erreur": str(e)}
        score, facteurs = predictions.score_risque(bien)
        return Response({"valorisation": val, "risque": {"score": score, "facteurs": facteurs}})

    @action(detail=False)
    def export(self, request):
        qs = self.filter_queryset(self.get_queryset())
        rep = HttpResponse(content_type="text/csv; charset=utf-8")
        rep["Content-Disposition"] = 'attachment; filename="umurage_inventaire.csv"'
        rep.write("﻿")  # pour qu'Excel lise les accents
        w = csv.writer(rep, delimiter=";")
        w.writerow(["Code", "Nom", "Catégorie", "Type", "District", "Paroisse", "État", "Statut juridique",
                    "Surface m²", "Date acquisition", "Valeur acquisition BIF", "Valeur estimée BIF",
                    "Score risque", "Latitude", "Longitude", "Financeur", "Bénéficiaires", "Responsable"])
        for b in qs:
            w.writerow([b.code, b.nom, b.get_categorie_display(), b.sous_type, b.district.nom,
                        b.paroisse.nom if b.paroisse else "", b.get_etat_display(), b.get_statut_juridique_display(),
                        b.surface_m2 or "", b.date_acquisition or "", b.valeur_acquisition, b.valeur_estimee or "",
                        b.score_risque if b.score_risque is not None else "", b.latitude or "", b.longitude or "",
                        b.financeur, b.beneficiaires, b.responsable])
        return rep


class MouvementViewSet(DistrictScopedMixin, JournalMixin, viewsets.ModelViewSet):
    queryset = Mouvement.objects.select_related("bien")
    serializer_class = MouvementSerializer
    district_field = "bien__district"
    roles_ecriture = ECRITURE_TERRAIN
    filterset_fields = ["bien", "type"]


class DocumentViewSet(DistrictScopedMixin, JournalMixin, viewsets.ModelViewSet):
    queryset = Document.objects.select_related("bien", "district")
    serializer_class = DocumentSerializer
    roles_ecriture = (R.ADMIN, R.SURINTENDANT, R.AGENT, R.TRESORIER, R.EVEQUE)
    filterset_fields = ["type", "bien", "district"]
    search_fields = ["titre", "contenu"]

    def get_queryset(self):
        # Les documents généraux (sans district) sont visibles par tous
        profil = profil_de(self.request.user)
        qs = Document.objects.select_related("bien", "district").filter(organisation_id=profil.organisation_id)
        if not profil.voit_tout:
            qs = qs.filter(Q(district_id=profil.district_id) | Q(district__isnull=True))
        return qs

    def perform_create(self, serializer):
        fichier = self.request.FILES.get("fichier")
        if fichier and not serializer.validated_data.get("contenu"):
            serializer.validated_data["contenu"] = extraire_texte(fichier)
        serializer.validated_data["organisation"] = profil_de(self.request.user).organisation
        super().perform_create(serializer)


class ProjetViewSet(DistrictScopedMixin, JournalMixin, viewsets.ModelViewSet):
    queryset = Projet.objects.select_related("district")
    serializer_class = ProjetSerializer
    roles_ecriture = (R.ADMIN, R.SURINTENDANT)
    filterset_fields = ["district", "domaine", "statut"]
    search_fields = ["nom", "description", "financeur"]
    pagination_class = None


# ---------------------------------------------------------------- Tableaux de bord
def _perimetre(request):
    profil = profil_de(request.user)
    org = profil.organisation_id
    biens = Bien.objects.filter(district__organisation_id=org, date_sortie__isnull=True)
    projets = Projet.objects.filter(district__organisation_id=org)
    trans = Transaction.objects.filter(district__organisation_id=org)
    district = request.query_params.get("district")
    if profil and not profil.voit_tout:
        district = profil.district_id
    if district:
        biens, projets, trans = biens.filter(district=district), projets.filter(district=district), trans.filter(district=district)
    return biens, projets, trans


def _impact_odd(biens, projets):
    # Seules deux colonnes sont lues : on évite de charger chaque bien et chaque projet en entier
    impact = defaultdict(lambda: {"biens": 0, "projets": 0, "beneficiaires": 0})
    lignes = [(odd, benef, "biens") for odd, benef in biens.values_list("odd", "beneficiaires")]
    lignes += [(odd, benef, "projets") for odd, benef in projets.values_list("odd", "beneficiaires")]
    for odd, benef, cle in lignes:
        for o in [x.strip() for x in odd.split(",") if x.strip()]:
            impact[o][cle] += 1
            impact[o]["beneficiaires"] += benef
    return [{"odd": o, "libelle": ODD_LIBELLES.get(o, f"ODD {o}"), **v} for o, v in sorted(impact.items(), key=lambda x: int(x[0]))]


# Valeur courante calculée par la base : estimation de l'IA si elle existe, sinon valeur d'acquisition
VALEUR = Coalesce("valeur_estimee", "valeur_acquisition")
LIBELLES_CATEGORIES = dict(Bien.Categorie.choices)
SANTE = "centre de santé"


@api_view(["GET"])
def tableau_de_bord(request):
    profil = profil_de(request.user)
    district = request.query_params.get("district")
    if profil and not profil.voit_tout:
        district = profil.district_id
    return Response(cache_donnees.en_cache("tdb", profil.organisation_id, district or "tout",
                                           calcul=lambda: _calculer_tableau_de_bord(request, profil)))


def _calculer_tableau_de_bord(request, profil):
    biens, projets, trans = _perimetre(request)

    # Répartitions par catégorie et par district : deux requêtes groupées au lieu d'une boucle sur chaque bien
    par_cat = {}
    for l in biens.values("categorie").annotate(nombre=Count("id"), valeur=Sum(VALEUR)):
        par_cat[LIBELLES_CATEGORIES.get(l["categorie"], l["categorie"])] = {"nombre": l["nombre"], "valeur": float(l["valeur"] or 0)}
    par_dist = {}
    for l in biens.values("district__nom").annotate(
        nombre=Count("id"), valeur=Sum(VALEUR),
        a_risque=Count("id", filter=Q(score_risque__gte=50)),
        sans_titre=Count("id", filter=Q(categorie="FON") & ~Q(statut_juridique="TITRE")),
    ):
        par_dist[l["district__nom"]] = {"nombre": l["nombre"], "valeur": float(l["valeur"] or 0),
                                        "a_risque": l["a_risque"], "sans_titre": l["sans_titre"]}
    valeur_totale = sum(v["valeur"] for v in par_cat.values())

    # Tendance mensuelle (12 derniers mois) pour les mini-courbes du tableau de bord
    mensuel = defaultdict(lambda: {"recettes": 0.0, "depenses": 0.0})
    for l in trans.annotate(m=TruncMonth("date")).values("m", "sens").annotate(t=Sum("montant_bif")):
        cle = l["m"].strftime("%Y-%m")
        mensuel[cle]["recettes" if l["sens"] == "RECETTE" else "depenses"] += float(l["t"])
    tendance = [{"mois": k, **v} for k, v in sorted(mensuel.items())][-12:]

    # Activité récente : entretiens, alertes et transactions signalées, du plus récent au plus ancien
    activite = [
        {"type": "mouvement", "date": m.date.isoformat(), "titre": f"{m.get_type_display()} — {m.bien.nom}",
         "detail": m.description, "lien": f"/biens/{m.bien_id}"}
        for m in Mouvement.objects.filter(bien__in=biens).exclude(type="ACQUISITION").select_related("bien").order_by("-date")[:5]
    ]
    activite += [
        {"type": "alerte", "date": a.date.isoformat(), "titre": a.message, "detail": a.get_niveau_display(), "lien": "/capteurs"}
        for a in Alerte.objects.filter(resolue=False, bien__in=biens).order_by("-date")[:4]
    ]
    activite += [
        {"type": "anomalie", "date": t.date.isoformat(), "titre": f"Transaction signalée — {t.tiers or t.get_categorie_display()}",
         "detail": (t.motifs_anomalie or [""])[0], "lien": "/finances"}
        for t in trans.filter(est_anomalie=True, verifiee=False).order_by("-date")[:4]
    ]
    activite.sort(key=lambda x: x["date"], reverse=True)

    # Indicateurs : une requête par table au lieu d'une requête par chiffre
    kb = biens.aggregate(
        nb_biens=Count("id"),
        sans_titre=Count("id", filter=Q(categorie="FON") & ~Q(statut_juridique="TITRE")),
        terrains=Count("id", filter=Q(categorie="FON")),
        risque_eleve=Count("id", filter=Q(score_risque__gte=50)),
        benef_inf=Sum("beneficiaires", filter=Q(categorie="INF")),
    )
    kp = projets.aggregate(en_cours=Count("id", filter=Q(statut="EN_COURS")), benef=Sum("beneficiaires"))
    kt = trans.aggregate(
        recettes=Sum("montant_bif", filter=Q(sens="RECETTE")),
        depenses=Sum("montant_bif", filter=Q(sens="DEPENSE")),
        anomalies=Count("id", filter=Q(est_anomalie=True, verifiee=False)),
    )

    # Objectif du Health Board : un centre de santé par district d'ici 2030 (une seule requête pour tous les districts)
    sante = Q(biens__sous_type__icontains=SANTE)
    objectif = [
        {"district": d.nom, "operationnels": d.ops, "en_construction": d.cons}
        for d in District.objects.filter(organisation_id=profil.organisation_id).annotate(
            ops=Count("biens", filter=sante & ~Q(biens__etat="CONSTRUCTION")),
            cons=Count("biens", filter=sante & Q(biens__etat="CONSTRUCTION")),
        ).order_by("nom")  # l'ordre par défaut n'est pas appliqué aux requêtes groupées
    ]

    return {
        "kpi": {
            "nb_biens": kb["nb_biens"],
            "valeur_totale": round(valeur_totale),
            "sans_titre": kb["sans_titre"],
            "terrains": kb["terrains"],
            "risque_eleve": kb["risque_eleve"],
            "projets_en_cours": kp["en_cours"],
            "beneficiaires": (kp["benef"] or 0) + (kb["benef_inf"] or 0),
            "recettes": float(kt["recettes"] or 0),
            "depenses": float(kt["depenses"] or 0),
            "anomalies": kt["anomalies"],
            "alertes": Alerte.objects.filter(resolue=False, bien__in=biens).count(),
        },
        "par_categorie": [{"categorie": k, **v} for k, v in sorted(par_cat.items(), key=lambda x: -x[1]["valeur"])],
        "par_district": [{"district": k, **v} for k, v in sorted(par_dist.items())],
        "tendance": tendance,
        "activite": activite[:10],
        "etats": list(biens.values("etat").annotate(n=Count("id")).order_by("etat")),
        "impact_odd": _impact_odd(biens, projets),
        # Copie en dictionnaires simples : le résultat doit pouvoir être mis en cache
        "biens_a_risque": [dict(b) for b in BienSerializer(
            biens.select_related("district", "paroisse").filter(score_risque__gte=50).order_by("-score_risque", "id")[:6], many=True
        ).data],
        "objectif_sante_2030": objectif,
    }


@api_view(["GET"])
def carte(request):
    """Points géolocalisés (biens et projets) pour la carte interactive."""
    profil = profil_de(request.user)
    district = profil.district_id if not profil.voit_tout else request.query_params.get("district")
    return Response(cache_donnees.en_cache("carte", profil.organisation_id, district or "tout", calcul=lambda: _points_carte(request)))


def _points_carte(request):
    biens, projets, _ = _perimetre(request)
    points = [
        {"type": "bien", "id": b.id, "nom": b.nom, "code": b.code, "categorie": b.categorie,
         "categorie_libelle": b.get_categorie_display(), "etat": b.etat, "district": b.district.nom,
         "lat": b.latitude, "lon": b.longitude, "valeur": float(b.valeur_courante or 0), "risque": b.score_risque}
        for b in biens.select_related("district").exclude(latitude=None)
    ]
    points += [
        {"type": "projet", "id": p.id, "nom": p.nom, "domaine": p.get_domaine_display(), "statut": p.get_statut_display(),
         "avancement": p.avancement, "district": p.district.nom, "lat": p.latitude, "lon": p.longitude}
        for p in projets.select_related("district").exclude(latitude=None)
    ]
    return points


@api_view(["GET"])
@permission_classes([AllowAny])
def portail_public(request):
    """
    Portail de transparence : uniquement des chiffres d'impact agrégés et les projets
    marqués « publics ». Aucune donnée financière détaillée ni titre foncier.
    """
    slug = request.query_params.get("organisation")
    orgs = Organisation.objects.filter(portail_public=True).exclude(statut="SUSPENDU")
    org = (orgs.filter(slug=slug) if slug else orgs.order_by("id")).first()
    if org is None:
        return Response({"erreur": "Portail introuvable."}, status=404)
    return Response(cache_donnees.en_cache("public", org.pk, calcul=lambda: _donnees_portail(org)))


def _donnees_portail(org):
    biens = Bien.objects.filter(district__organisation=org)
    projets = Projet.objects.filter(public=True, district__organisation=org).select_related("district")
    forages = biens.filter(sous_type__icontains="forage")
    return {
        "organisation": {"nom": org.nom, "sigle": org.sigle, "pays": org.pays, "slug": org.slug, "langue": org.langue},
        "chiffres": {
            "forages": forages.count(),
            "personnes_eau": sum(b.beneficiaires for b in forages),
            "centres_sante": biens.filter(sous_type__icontains="centre de santé").count(),
            # Comparaison en Python : SQLite ignore la casse seulement pour les lettres sans accent
            "ecoles": sum(1 for st in biens.values_list("sous_type", flat=True)
                          if any(m in st.lower() for m in ("école", "lycée", "université"))),
            "projets": projets.count(),
            "beneficiaires": sum(p.beneficiaires for p in projets),
            "districts": org.districts.count(),
        },
        "impact_odd": _impact_odd(biens, projets),
        "projets": [
            {"nom": p.nom, "domaine": p.get_domaine_display(), "district": p.district.nom, "statut": p.get_statut_display(),
             "avancement": p.avancement, "beneficiaires": p.beneficiaires, "financeur": p.financeur,
             "lat": p.latitude, "lon": p.longitude, "description": p.description}
            for p in projets
        ],
    }


@api_view(["GET"])
def recherche(request):
    """Recherche globale (barre Ctrl+K) : biens, projets, documents et paroisses du périmètre de l'utilisateur."""
    q = (request.query_params.get("q") or "").strip()
    if len(q) < 2:
        return Response([])
    profil = profil_de(request.user)
    limite = Q(district__organisation_id=profil.organisation_id)
    if not profil.voit_tout:
        limite &= Q(district_id=profil.district_id)
    res = [
        {"type": "Bien", "titre": b.nom, "detail": f"{b.code} — {b.district.nom}", "lien": f"/biens/{b.id}"}
        for b in Bien.objects.filter(limite).filter(Q(nom__icontains=q) | Q(code__icontains=q) | Q(sous_type__icontains=q)).select_related("district")[:8]
    ]
    res += [
        {"type": "Projet", "titre": p.nom, "detail": f"{p.get_domaine_display()} — {p.district.nom}", "lien": "/projets"}
        for p in Projet.objects.filter(limite).filter(Q(nom__icontains=q) | Q(financeur__icontains=q)).select_related("district")[:5]
    ]
    docs = Document.objects.filter(organisation_id=profil.organisation_id, titre__icontains=q)
    if not profil.voit_tout:
        docs = docs.filter(Q(district_id=profil.district_id) | Q(district__isnull=True))
    res += [{"type": "Document", "titre": d.titre, "detail": d.get_type_display(), "lien": "/assistant"} for d in docs[:5]]
    return Response(res)


@api_view(["GET"])
def compteurs(request):
    """Petits compteurs affichés dans la navigation."""
    biens, _, trans = _perimetre(request)
    profil = profil_de(request.user)
    decl = Declaration.objects.filter(organisation_id=profil.organisation_id, statut="EN_ATTENTE")
    if not profil.voit_tout:
        decl = decl.filter(district_id=profil.district_id)
    return Response({
        "alertes": Alerte.objects.filter(resolue=False, bien__in=biens).count(),
        "alertes_critiques": Alerte.objects.filter(resolue=False, bien__in=biens, niveau="CRITIQUE").count(),
        "anomalies": trans.filter(est_anomalie=True, verifiee=False).count(),
        "declarations": decl.count(),
    })
