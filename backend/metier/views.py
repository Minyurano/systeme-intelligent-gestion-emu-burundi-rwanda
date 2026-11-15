from datetime import date, timedelta

from django.db import transaction as db_transaction
from django.db.models import F, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action, api_view, parser_classes, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from core.models import District, Profil
from core.securite import DistrictScopedMixin, JournalMixin, RolePermission, profil_de
from finances.models import Transaction
from patrimoine.models import Bien, Document, Mouvement

from . import comparaison, comptabilite, services, statistiques as stats_eglise, taches
from .models import (
    Avis, Bail, Budget, Campagne, ClotureExercice, Constat, Demande, DemandeAcces, Echeance, Fournisseur, Loyer, MembreEglise, OrdreTravail,
    PlanMaintenance, ajouter_mois,
)
from .serializers import (
    BailSerializer, BudgetSerializer, CampagneSerializer, ClotureSerializer, ConstatSerializer, DemandeSerializer,
    EcheanceSerializer, FournisseurSerializer, LoyerSerializer, MembreEgliseSerializer, OrdreTravailSerializer,
    PlanMaintenanceSerializer,
)

R = Profil.Role
TOUS = (R.ADMIN, R.EVEQUE, R.TRESORIER, R.SURINTENDANT, R.AGENT)


class OrganisationDistrictMixin(JournalMixin):
    """
    Objets rattachés à une organisation et, facultativement, à un district.
    Un surintendant ou un agent voit son district et ce qui concerne toute l'organisation.
    """

    permission_classes = [RolePermission]
    district_field = "district"

    def get_queryset(self):
        profil = profil_de(self.request.user)
        qs = super().get_queryset().filter(organisation_id=profil.organisation_id)
        if not profil.voit_tout:
            qs = qs.filter(Q(district_id=profil.district_id) | Q(district__isnull=True))
        return qs

    def perform_create(self, serializer):
        profil = profil_de(self.request.user)
        self._verifier_district(serializer)
        if not profil.voit_tout and serializer.validated_data.get("district") is None and "district" in serializer.fields:
            serializer.validated_data["district"] = profil.district
        instance = serializer.save(organisation_id=profil.organisation_id)
        self._journaliser("CREATION", instance)


# ====================================================================== 1. Approbations
class DemandeViewSet(OrganisationDistrictMixin, mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """Une demande ne se modifie pas : elle se valide, se rejette, s'exécute ou s'annule. Tout est tracé."""

    queryset = Demande.objects.select_related("district", "district_destination", "bien", "demandeur").prefetch_related("avis__utilisateur")
    serializer_class = DemandeSerializer
    roles_ecriture = TOUS
    filterset_fields = ["statut", "type", "district"]
    search_fields = ["titre", "description"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("a_valider") == "1":
            profil = profil_de(self.request.user)
            ids = [d.pk for d in qs.filter(statut=Demande.Statut.EN_ATTENTE) if services.peut_valider(profil, d)]
            qs = qs.filter(pk__in=ids)
        return qs

    def perform_create(self, serializer):
        profil = profil_de(self.request.user)
        self._verifier_district(serializer)
        d = serializer.validated_data.get("district") or profil.district
        if d is None:
            raise ValidationError({"district": "Indiquez le district concerné."})
        bien = serializer.validated_data.get("bien")
        if bien and bien.district_id != d.pk:
            raise ValidationError({"bien": "Ce bien n'appartient pas au district de la demande."})
        donnees = {**serializer.validated_data, "district": d}
        demande = Demande(**donnees, organisation_id=profil.organisation_id, demandeur=self.request.user)
        with db_transaction.atomic():
            services.creer_demande(demande)
            serializer.instance = demande
            self._journaliser("CREATION", demande, {"circuit": demande.circuit})

    def _repondre(self, demande):
        demande.refresh_from_db()
        return Response(self.get_serializer(demande).data)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        demande = self.get_object()
        decision = Avis.Decision.REJETE if request.data.get("decision") == "REJETE" else Avis.Decision.APPROUVE
        services.decider(demande, profil_de(request.user), decision, request.data.get("commentaire", ""))
        self._journaliser("MODIFICATION", demande, {"decision": decision, "commentaire": request.data.get("commentaire", "")})
        return self._repondre(demande)

    @action(detail=True, methods=["post"])
    def executer(self, request, pk=None):
        demande = self.get_object()
        services.executer(demande, profil_de(request.user))
        self._journaliser("MODIFICATION", demande, {"execution": demande.resultat})
        return self._repondre(demande)

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        demande = self.get_object()
        if demande.demandeur_id != request.user.pk or demande.statut != Demande.Statut.EN_ATTENTE:
            raise PermissionDenied("Seul le demandeur peut annuler une demande encore en attente.")
        demande.statut = Demande.Statut.ANNULEE
        demande.save(update_fields=["statut"])
        self._journaliser("MODIFICATION", demande, {"statut": "ANNULEE"})
        return self._repondre(demande)


# ====================================================================== 2. Échéancier
class EcheanceViewSet(OrganisationDistrictMixin, viewsets.ModelViewSet):
    queryset = Echeance.objects.select_related("bien", "district", "responsable")
    serializer_class = EcheanceSerializer
    roles_ecriture = (R.ADMIN, R.EVEQUE, R.TRESORIER, R.SURINTENDANT)
    filterset_fields = {"statut": ["exact"], "type": ["exact"], "district": ["exact"], "bien": ["exact"], "date": ["gte", "lte"]}
    search_fields = ["libelle"]
    pagination_class = None

    @action(detail=True, methods=["post"])
    def faite(self, request, pk=None):
        e = self.get_object()
        suivante = services.marquer_faite(e)
        self._journaliser("MODIFICATION", e, {"statut": "FAIT", "suivante": suivante.date.isoformat() if suivante else None})
        return Response({"echeance": self.get_serializer(e).data,
                         "suivante": self.get_serializer(suivante).data if suivante else None})


# ====================================================================== 3. Baux et loyers
class BailViewSet(DistrictScopedMixin, JournalMixin, viewsets.ModelViewSet):
    queryset = Bail.objects.select_related("bien", "bien__district").prefetch_related("loyers")
    serializer_class = BailSerializer
    district_field = "bien__district"
    roles_ecriture = (R.ADMIN, R.TRESORIER, R.SURINTENDANT)
    filterset_fields = ["statut", "bien"]
    search_fields = ["locataire", "objet", "bien__nom"]
    pagination_class = None

    def perform_create(self, serializer):
        super().perform_create(serializer)
        serializer.instance.generer_loyers()

    @action(detail=True, methods=["post"])
    def terminer(self, request, pk=None):
        bail = self.get_object()
        bail.statut, bail.date_fin = Bail.Statut.TERMINE, bail.date_fin or date.today()
        bail.save(update_fields=["statut", "date_fin"])
        self._journaliser("MODIFICATION", bail, {"statut": "TERMINE"})
        return Response(self.get_serializer(bail).data)


class LoyerViewSet(DistrictScopedMixin, JournalMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Loyer.objects.select_related("bail", "bail__bien", "bail__bien__district")
    serializer_class = LoyerSerializer
    district_field = "bail__bien__district"
    roles_ecriture = (R.ADMIN, R.TRESORIER, R.SURINTENDANT)
    filterset_fields = ["bail"]
    pagination_class = None

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("impayes") == "1":
            qs = qs.filter(echeance__lt=date.today()).filter(montant_paye__lt=F("montant_du"))
        return qs

    @action(detail=True, methods=["post"])
    def payer(self, request, pk=None):
        """Encaisse un loyer : la recette est enregistrée dans les finances, rattachée au bien."""
        if profil_de(request.user).role not in self.roles_ecriture:
            raise PermissionDenied("Votre rôle ne permet pas d'encaisser un loyer.")
        loyer = self.get_object()
        montant = comptabilite._nombre(request.data.get("montant")) or loyer.reste
        if montant <= 0:
            raise ValidationError({"montant": "Montant invalide."})
        jour = date.fromisoformat(request.data["date"]) if request.data.get("date") else date.today()
        bien = loyer.bail.bien
        services.verifier_exercice_ouvert(bien.district.organisation_id, jour)
        with db_transaction.atomic():
            t = Transaction.objects.create(
                date=jour, sens=Transaction.Sens.RECETTE, categorie=Transaction.Categorie.LOYER, montant=montant,
                devise=bien.district.organisation.devise, district=bien.district, bien=bien,
                canal=request.data.get("canal") or Transaction.Canal.ESPECES, reference_externe=request.data.get("reference", "")[:60],
                tiers=loyer.bail.locataire[:120], description=f"Loyer {loyer.periode:%m/%Y} — {loyer.bail.objet or bien.nom}"[:255],
            )
            loyer.montant_paye += montant
            loyer.paye_le, loyer.transaction = jour, t
            loyer.save(update_fields=["montant_paye", "paye_le", "transaction"])
        self._journaliser("MODIFICATION", loyer.bail, {"loyer": loyer.periode.isoformat(), "paye": str(montant)})
        return Response(self.get_serializer(loyer).data)


# ====================================================================== 4. Maintenance
class FournisseurViewSet(JournalMixin, viewsets.ModelViewSet):
    queryset = Fournisseur.objects.all()
    serializer_class = FournisseurSerializer
    permission_classes = [RolePermission]
    roles_ecriture = (R.ADMIN, R.TRESORIER, R.SURINTENDANT)
    search_fields = ["nom", "specialite"]
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().filter(organisation_id=profil_de(self.request.user).organisation_id)

    def perform_create(self, serializer):
        instance = serializer.save(organisation_id=profil_de(self.request.user).organisation_id)
        self._journaliser("CREATION", instance)


class PlanMaintenanceViewSet(DistrictScopedMixin, JournalMixin, viewsets.ModelViewSet):
    queryset = PlanMaintenance.objects.select_related("bien", "fournisseur")
    serializer_class = PlanMaintenanceSerializer
    district_field = "bien__district"
    roles_ecriture = (R.ADMIN, R.SURINTENDANT)
    filterset_fields = ["bien", "actif"]
    pagination_class = None


class OrdreTravailViewSet(DistrictScopedMixin, JournalMixin, viewsets.ModelViewSet):
    queryset = OrdreTravail.objects.select_related("bien", "bien__district", "fournisseur")
    serializer_class = OrdreTravailSerializer
    district_field = "bien__district"
    roles_ecriture = (R.ADMIN, R.SURINTENDANT, R.AGENT, R.TRESORIER)
    filterset_fields = ["statut", "priorite", "origine", "bien", "fournisseur"]
    search_fields = ["titre", "description", "bien__nom", "bien__code"]
    pagination_class = None

    def perform_create(self, serializer):
        super().perform_create(serializer)
        serializer.instance.cree_par = self.request.user
        serializer.instance.save(update_fields=["cree_par"])

    @action(detail=True, methods=["post"])
    def terminer(self, request, pk=None):
        """Clôt le travail : il entre dans l'historique du bien et, si demandé, la dépense est enregistrée."""
        ot = self.get_object()
        if ot.statut in (OrdreTravail.Statut.TERMINE, OrdreTravail.Statut.ANNULE):
            raise ValidationError("Cet ordre de travail est déjà clos.")
        jour = date.fromisoformat(request.data["date"]) if request.data.get("date") else date.today()
        cout = comptabilite._nombre(request.data.get("cout_reel")) if request.data.get("cout_reel") not in (None, "") else ot.cout_estime
        with db_transaction.atomic():
            ot.statut, ot.termine_le, ot.cout_reel = OrdreTravail.Statut.TERMINE, jour, cout
            ot.rapport = request.data.get("rapport", ot.rapport)
            Mouvement.objects.create(bien=ot.bien, type=ot.type, date=jour,
                                     montant=cout or 0, description=f"OT-{ot.pk} {ot.titre}. {ot.rapport}".strip(),
                                     auteur=ot.fournisseur.nom if ot.fournisseur else (request.user.get_full_name() or request.user.username))
            # Seule la trésorerie écrit dans les finances (séparation des tâches)
            if cout and str(request.data.get("enregistrer_depense", "")).lower() in ("1", "true", "oui") \
                    and profil_de(request.user).role in (R.ADMIN, R.TRESORIER):
                services.verifier_exercice_ouvert(ot.bien.district.organisation_id, jour)
                ot.transaction = Transaction.objects.create(
                    date=jour, sens=Transaction.Sens.DEPENSE, categorie=Transaction.Categorie.MAINTENANCE, montant=cout,
                    devise=ot.bien.district.organisation.devise, district=ot.bien.district, bien=ot.bien,
                    tiers=ot.fournisseur.nom[:120] if ot.fournisseur else "", description=f"OT-{ot.pk} {ot.titre}"[:255],
                )
            ot.save()
            if ot.plan_id:
                plan = ot.plan
                plan.prochaine_date = ajouter_mois(jour, plan.periodicite_mois)
                plan.save(update_fields=["prochaine_date"])
        self._journaliser("MODIFICATION", ot, {"statut": "TERMINE", "cout": str(cout)})
        return Response(self.get_serializer(ot).data)

    @action(detail=False, methods=["post"])
    def depuis_risques(self, request):
        """Ouvre un ordre d'inspection pour chaque bien à risque élevé qui n'en a pas encore."""
        profil = profil_de(request.user)
        if profil.role not in (R.ADMIN, R.SURINTENDANT, R.EVEQUE):
            raise PermissionDenied()
        return Response({"crees": taches.ordres_depuis_risques(date.today(), profil.organisation_id)})


# ====================================================================== 5. Comptabilité du patrimoine
class BudgetViewSet(JournalMixin, viewsets.ModelViewSet):
    queryset = Budget.objects.select_related("district", "projet")
    serializer_class = BudgetSerializer
    permission_classes = [RolePermission]
    roles_ecriture = (R.ADMIN, R.TRESORIER)
    filterset_fields = ["annee", "district", "sens"]
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().filter(organisation_id=profil_de(self.request.user).organisation_id)

    def perform_create(self, serializer):
        self._verifier_district(serializer)
        instance = serializer.save(organisation_id=profil_de(self.request.user).organisation_id)
        self._journaliser("CREATION", instance)

    @action(detail=False)
    def suivi(self, request):
        profil = profil_de(request.user)
        annee = int(request.query_params.get("annee") or date.today().year)
        district = request.query_params.get("district") if profil.voit_tout else profil.district_id
        return Response(comptabilite.suivi_budget(profil.organisation_id, annee, district))


class ClotureViewSet(JournalMixin, mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = ClotureExercice.objects.all()
    serializer_class = ClotureSerializer
    permission_classes = [RolePermission]
    roles_ecriture = (R.ADMIN, R.TRESORIER)
    pagination_class = None

    def get_queryset(self):
        return super().get_queryset().filter(organisation_id=profil_de(self.request.user).organisation_id)

    def perform_create(self, serializer):
        profil = profil_de(self.request.user)
        annee = serializer.validated_data["annee"]
        if annee >= date.today().year:
            raise ValidationError({"annee": "Seul un exercice terminé peut être clôturé."})
        if ClotureExercice.objects.filter(organisation_id=profil.organisation_id, annee=annee).exists():
            raise ValidationError({"annee": "Cet exercice est déjà clôturé."})
        instance = serializer.save(organisation_id=profil.organisation_id, cloture_par=self.request.user,
                                   totaux=comptabilite.totaux_exercice(profil.organisation_id, annee))
        self._journaliser("CREATION", instance, {"annee": annee, "totaux": instance.totaux})


def _profil_compta(request):
    profil = profil_de(request.user)
    if profil is None or profil.role not in (R.ADMIN, R.TRESORIER, R.EVEQUE):
        raise PermissionDenied("Réservé à la direction et à la trésorerie.")
    return profil


@api_view(["GET"])
def registre_immobilisations(request):
    profil = _profil_compta(request)
    annee = int(request.query_params.get("annee") or date.today().year)
    donnees = comptabilite.registre(Bien.objects.filter(district__organisation_id=profil.organisation_id), annee)
    if request.query_params.get("export") == "csv":
        rep = HttpResponse(comptabilite.registre_csv(donnees), content_type="text/csv; charset=utf-8")
        rep["Content-Disposition"] = f'attachment; filename="registre_immobilisations_{annee}.csv"'
        return rep
    return Response(donnees)


@api_view(["POST"])
@parser_classes([MultiPartParser])
def rapprochement(request):
    profil = profil_de(request.user)
    if profil is None or profil.role not in (R.ADMIN, R.TRESORIER):
        raise PermissionDenied("Réservé à la trésorerie.")
    fichier = request.FILES.get("fichier")
    if not fichier:
        raise ValidationError({"fichier": "Joignez le relevé au format CSV."})
    brut = fichier.read()
    try:
        texte = brut.decode("utf-8")
    except UnicodeDecodeError:
        texte = brut.decode("latin-1")
    res = comptabilite.rapprocher(profil.organisation_id, texte)
    if "erreur" in res:
        raise ValidationError(res["erreur"])
    return Response(res)


# ====================================================================== 6. Campagnes d'inventaire
class CampagneViewSet(OrganisationDistrictMixin, viewsets.ModelViewSet):
    queryset = Campagne.objects.select_related("district")
    serializer_class = CampagneSerializer
    roles_ecriture = (R.ADMIN, R.SURINTENDANT, R.EVEQUE)
    pagination_class = None

    def _biens(self, c):
        qs = Bien.objects.filter(district__organisation_id=c.organisation_id, date_sortie__isnull=True)
        return qs.filter(district_id=c.district_id) if c.district_id else qs

    @action(detail=True, methods=["post"])
    def scanner(self, request, pk=None):
        """Un agent scanne le QR code (ou tape le code) d'un bien sur le terrain."""
        c = self.get_object()
        profil = profil_de(request.user)
        if c.statut != Campagne.Statut.OUVERTE:
            raise ValidationError("Cette campagne est clôturée.")
        code = (request.data.get("code") or "").strip().upper()
        bien = self._biens(c).filter(code__iexact=code).first() or self._biens(c).filter(pk=request.data.get("bien") or 0).first()
        if bien is None:
            raise ValidationError({"code": f"Aucun bien « {code} » dans le périmètre de cette campagne."})
        if not profil.voit_tout and bien.district_id != profil.district_id:
            raise PermissionDenied("Ce bien n'est pas dans votre district.")
        trouve = str(request.data.get("trouve", "true")).lower() not in ("false", "0", "non")
        constat, _ = Constat.objects.update_or_create(
            campagne=c, bien=bien,
            defaults={"trouve": trouve, "etat_constate": request.data.get("etat_constate") or "",
                      "commentaire": (request.data.get("commentaire") or "")[:255], "agent": request.user},
        )
        return Response(ConstatSerializer(constat).data)

    @action(detail=True)
    def ecarts(self, request, pk=None):
        c = self.get_object()
        return Response(self._ecarts(c))

    def _ecarts(self, c):
        biens = self._biens(c)
        constats = {k.bien_id: k for k in c.constats.select_related("bien", "agent")}
        non_vus = [{"id": b.pk, "code": b.code, "nom": b.nom, "district": b.district.nom}
                   for b in biens.select_related("district") if b.pk not in constats]
        introuvables = [ConstatSerializer(k).data for k in constats.values() if not k.trouve]
        etats = [ConstatSerializer(k).data for k in constats.values() if k.trouve and k.etat_constate and k.etat_constate != k.bien.etat]
        total = biens.count()
        return {"biens": total, "vus": len(constats), "avancement": round(100 * len(constats) / total) if total else 100,
                "non_vus": non_vus, "introuvables": introuvables, "etats_differents": etats,
                "conformes": sum(1 for k in constats.values() if k.trouve and (not k.etat_constate or k.etat_constate == k.bien.etat))}

    @action(detail=True, methods=["post"])
    def cloturer(self, request, pk=None):
        """Fige le procès-verbal ; peut appliquer à l'inventaire les états constatés sur le terrain."""
        c = self.get_object()
        profil = profil_de(request.user)
        if profil.role not in self.roles_ecriture:
            raise PermissionDenied()
        if c.statut == Campagne.Statut.CLOTUREE:
            raise ValidationError("Déjà clôturée.")
        pv = self._ecarts(c)
        appliquer = str(request.data.get("appliquer_etats", "")).lower() in ("1", "true", "oui")
        with db_transaction.atomic():
            if appliquer:
                for e in pv["etats_differents"]:
                    b = Bien.objects.get(pk=e["bien"])
                    Mouvement.objects.create(bien=b, type=Mouvement.Type.INSPECTION, date=date.today(),
                                             description=f"Inventaire « {c.nom} » : état {b.get_etat_display()} → {dict(Bien.Etat.choices)[e['etat_constate']]}",
                                             auteur=e.get("agent_nom") or "")
                    b.etat = e["etat_constate"]
                    b.save(update_fields=["etat"])
            for e in pv["introuvables"]:
                b = Bien.objects.get(pk=e["bien"])
                OrdreTravail.objects.get_or_create(
                    bien=b, origine=OrdreTravail.Origine.INVENTAIRE, statut=OrdreTravail.Statut.DEMANDE,
                    defaults={"titre": f"Bien introuvable lors de l'inventaire — {b.nom}", "type": OrdreTravail.Type.INSPECTION,
                              "priorite": OrdreTravail.Priorite.HAUTE, "description": e.get("commentaire", "")},
                )
            c.statut, c.cloturee_le = Campagne.Statut.CLOTUREE, timezone.now()
            c.proces_verbal = {**pv, "etats_appliques": appliquer, "cloture_par": request.user.get_full_name() or request.user.username,
                               "date": timezone.now().isoformat()}
            c.save()
        self._journaliser("MODIFICATION", c, {"cloture": True, "etats_appliques": appliquer})
        return Response(self.get_serializer(c).data)


# ====================================================================== 7. Documents obligatoires
DOCUMENTS_OBLIGATOIRES = {
    "FON": [("TITRE_FONCIER", "Titre foncier", lambda b: b.statut_juridique == "TITRE")],
    "VEH": [("CARTE_GRISE", "Carte grise", lambda b: True), ("ASSURANCE", "Attestation d'assurance", lambda b: True)],
    "IMM": [("ASSURANCE", "Attestation d'assurance", lambda b: (b.valeur_courante or 0) >= 50_000_000)],
}


@api_view(["GET"])
def documents_manquants(request):
    """Pièces exigées par catégorie de bien et absentes (ou expirées) du dossier."""
    profil = profil_de(request.user)
    biens = Bien.objects.filter(district__organisation_id=profil.organisation_id, date_sortie__isnull=True,
                                categorie__in=DOCUMENTS_OBLIGATOIRES).select_related("district")
    if not profil.voit_tout:
        biens = biens.filter(district_id=profil.district_id)
    valides = {}
    for bien_id, type_doc, exp in Document.objects.filter(bien__in=biens).values_list("bien_id", "type", "date_expiration"):
        if exp is None or exp >= date.today():
            valides.setdefault(bien_id, set()).add(type_doc)
    manquants = []
    for b in biens:
        for type_doc, libelle, exige in DOCUMENTS_OBLIGATOIRES[b.categorie]:
            if exige(b) and type_doc not in valides.get(b.pk, set()):
                manquants.append({"bien": b.pk, "code": b.code, "nom": b.nom, "district": b.district.nom,
                                  "document": type_doc, "libelle": libelle})
    expirant = Document.objects.filter(organisation_id=profil.organisation_id, date_expiration__isnull=False,
                                       date_expiration__lte=date.today() + timedelta(days=60)).order_by("date_expiration")
    return Response({"manquants": manquants, "expirent_bientot": [
        {"id": d.pk, "titre": d.titre, "type": d.get_type_display(), "date_expiration": d.date_expiration, "bien": d.bien_id}
        for d in expirant[:50]
    ]})


# ====================================================================== Comparaison des églises
@api_view(["GET"])
def comparer_eglises(request):
    """Compare les paroisses (églises locales) ou les districts de l'organisation, dans le périmètre de l'utilisateur."""
    profil = profil_de(request.user)
    niveau = "district" if request.query_params.get("niveau") == "district" else "paroisse"
    district = request.query_params.get("district") if profil.voit_tout else profil.district_id
    annee = int(request.query_params.get("annee") or date.today().year)
    return Response(comparaison.comparer(profil.organisation_id, niveau, district or None, annee))


@api_view(["GET"])
def analyse_comparaison(request):
    """Analyse par apprentissage automatique de la comparaison (profils, carte, indice attendu, atypiques, jumelles)."""
    from . import analyse_ml

    profil = profil_de(request.user)
    niveau = "district" if request.query_params.get("niveau") == "district" else "paroisse"
    district = request.query_params.get("district") if profil.voit_tout else profil.district_id
    annee = int(request.query_params.get("annee") or date.today().year)
    return Response(analyse_ml.analyser(profil.organisation_id, niveau, district or None, annee))


# ====================================================================== Statistiques de l'Église
@api_view(["GET"])
def statistiques_eglise(request):
    """Tableau de bord statistique : membres, comparaison d'une année sur l'autre, districts, patrimoine, finances."""
    profil = profil_de(request.user)
    if profil is None or profil.organisation_id is None:
        raise PermissionDenied()
    d = request.query_params.get("district")
    district = int(d) if d and d.isdigit() and District.objects.filter(pk=d, organisation_id=profil.organisation_id).exists() else None
    return Response(stats_eglise.statistiques(profil, district))


# ====================================================================== Vue d'ensemble et tâches
@api_view(["GET"])
def compteurs_metier(request):
    profil = profil_de(request.user)
    org = profil.organisation_id
    demandes = Demande.objects.filter(organisation_id=org, statut=Demande.Statut.EN_ATTENTE).prefetch_related("avis")
    a_valider = sum(1 for d in demandes if services.peut_valider(profil, d))
    a_executer = sum(1 for d in Demande.objects.filter(organisation_id=org, statut=Demande.Statut.APPROUVEE) if services.peut_executer(profil, d))
    ech = Echeance.objects.filter(organisation_id=org, statut=Echeance.Statut.A_FAIRE, date__lte=date.today() + timedelta(days=7))
    loyers = Loyer.objects.filter(bail__bien__district__organisation_id=org, echeance__lt=date.today()).filter(montant_paye__lt=F("montant_du"))
    ot = OrdreTravail.objects.filter(bien__district__organisation_id=org, statut__in=OrdreTravail.OUVERTS,
                                     priorite__in=[OrdreTravail.Priorite.HAUTE, OrdreTravail.Priorite.URGENTE])
    if not profil.voit_tout:
        ech = ech.filter(Q(district_id=profil.district_id) | Q(district__isnull=True))
        loyers = loyers.filter(bail__bien__district_id=profil.district_id)
        ot = ot.filter(bien__district_id=profil.district_id)
    # Gravité : chaque compteur indique aussi s'il contient des éléments critiques (voyant rouge clignotant)
    return Response({
        "approbations": a_valider + a_executer,
        "echeances": ech.count(), "echeances_retard": ech.filter(date__lt=date.today()).count(),
        "loyers_impayes": loyers.count(), "loyers_impayes_anciens": loyers.filter(echeance__lt=date.today() - timedelta(days=60)).count(),
        "ordres_urgents": ot.count(), "ordres_critiques": ot.filter(priorite=OrdreTravail.Priorite.URGENTE).count(),
        # Demandes d'accès des fidèles (visibles des seuls administrateurs)
        "demandes_acces": DemandeAcces.objects.filter(organisation_id=org, statut=DemandeAcces.Statut.EN_ATTENTE).count()
        if profil.role == R.ADMIN else 0,
    })


@api_view(["POST"])
def executer_taches(request):
    profil = profil_de(request.user)
    if profil is None or profil.role != R.ADMIN:
        raise PermissionDenied("Réservé à l'administrateur.")
    return Response(taches.executer_tout())


# ====================================================================== 7. Registre des membres
class MembreEgliseViewSet(DistrictScopedMixin, JournalMixin, viewsets.ModelViewSet):
    """
    Registre officiel : les pasteurs, agents et surintendants enregistrent les membres de leurs églises locales.
    Une fiche ne se supprime pas (sauf administrateur) : on change son statut (transféré, décédé).
    """

    queryset = MembreEglise.objects.select_related("paroisse", "paroisse__district", "enregistre_par")
    serializer_class = MembreEgliseSerializer
    district_field = "paroisse__district"
    roles_ecriture = (R.ADMIN, R.EVEQUE, R.SURINTENDANT, R.AGENT)
    filterset_fields = ["paroisse", "statut", "sexe", "paroisse__district"]
    search_fields = ["nom", "prenom", "numero", "telephone", "adresse"]
    ordering_fields = ["nom", "numero", "date_adhesion", "cree_le"]

    def perform_create(self, serializer):
        self._verifier_district(serializer)
        instance = serializer.save(enregistre_par=self.request.user)
        self._journaliser("CREATION", instance)

    def perform_destroy(self, instance):
        if profil_de(self.request.user).role != R.ADMIN:
            raise PermissionDenied("Une fiche de membre ne se supprime pas : changez son statut (transféré, décédé).")
        self._journaliser("SUPPRESSION", instance)
        instance.delete()

    @action(detail=False)
    def statistiques(self, request):
        from django.db.models import Count
        qs = self.filter_queryset(self.get_queryset())
        actifs = qs.filter(statut__in=MembreEglise.ACTIFS)
        par_statut = dict(qs.values_list("statut").annotate(n=Count("id")))
        par_sexe = dict(actifs.values_list("sexe").annotate(n=Count("id")))
        debut_mois = date.today().replace(day=1)
        # Taux d'enregistrement : fiches actives / effectif déclaré de chaque église locale
        from core.models import Paroisse
        profil = profil_de(request.user)
        paroisses = Paroisse.objects.filter(district__organisation_id=profil.organisation_id).select_related("district")
        if not profil.voit_tout:
            paroisses = paroisses.filter(district_id=profil.district_id)
        inscrits = dict(actifs.values_list("paroisse").annotate(n=Count("id")))
        eglises = sorted(({
            "id": p.pk, "nom": p.nom, "district": p.district.nom, "declares": p.membres, "inscrits": inscrits.get(p.pk, 0),
            "taux": round(100 * inscrits.get(p.pk, 0) / p.membres, 1) if p.membres else None,
        } for p in paroisses), key=lambda e: -(e["inscrits"]))
        declares = sum(e["declares"] for e in eglises)
        return Response({
            "total": qs.count(), "actifs": actifs.count(),
            "baptises": actifs.filter(statut__in=[MembreEglise.Statut.BAPTISE, MembreEglise.Statut.CONFESSANT]).count(),
            "nouveaux_mois": qs.filter(cree_le__date__gte=debut_mois).count(),
            "hommes": par_sexe.get("H", 0), "femmes": par_sexe.get("F", 0),
            "par_statut": [{"statut": k, "libelle": l, "n": par_statut.get(k, 0)} for k, l in MembreEglise.Statut.choices],
            "declares": declares, "taux_enregistrement": round(100 * actifs.count() / declares, 2) if declares else None,
            "eglises": eglises,
        })
