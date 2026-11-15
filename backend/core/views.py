from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes, throttle_classes
from rest_framework.exceptions import PermissionDenied
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErreurDjango
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .jetons import nouvelle_session, revoquer_tout
from .models import District, JournalAction, Organisation, Paroisse, Profil
from .securite import DistrictScopedMixin, JournalMixin, OrganisationScopedMixin, RolePermission, profil_de
from .serializers import (
    DistrictSerializer, InscriptionSerializer, JournalSerializer, MembreSerializer, OrganisationSerializer, ParoisseSerializer,
)

R = Profil.Role


class DistrictViewSet(OrganisationScopedMixin, JournalMixin, viewsets.ModelViewSet):
    queryset = District.objects.all()
    serializer_class = DistrictSerializer
    pagination_class = None

    def perform_create(self, serializer):
        instance = serializer.save(organisation=profil_de(self.request.user).organisation)
        self._journaliser("CREATION", instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._journaliser("MODIFICATION", instance)


class ParoisseViewSet(DistrictScopedMixin, JournalMixin, viewsets.ModelViewSet):
    queryset = Paroisse.objects.select_related("district")
    serializer_class = ParoisseSerializer
    roles_ecriture = (R.ADMIN, R.SURINTENDANT)
    filterset_fields = ["district"]
    search_fields = ["nom", "pasteur"]
    pagination_class = None


class JournalViewSet(viewsets.ReadOnlyModelViewSet):
    """Journal d'audit chaîné (lecture seule), limité à l'organisation."""

    queryset = JournalAction.objects.select_related("utilisateur")
    serializer_class = JournalSerializer
    filterset_fields = ["action", "objet_type"]
    search_fields = ["objet_libelle"]

    def get_queryset(self):
        profil = profil_de(self.request.user)
        if not profil or profil.role not in (R.ADMIN, R.EVEQUE):
            raise PermissionDenied("Le journal d'audit est réservé à la direction.")
        return super().get_queryset().filter(organisation_id=profil.organisation_id)

    @action(detail=False)
    def verifier(self, request):
        self.get_queryset()  # contrôle d'accès
        intact, valeur = JournalAction.verifier_chaine()
        if intact:
            return Response({"intact": True, "entrees": valeur})
        return Response({"intact": False, "premiere_entree_alteree": valeur})


class MembreViewSet(JournalMixin, mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """Comptes des membres de l'organisation, gérés par son administrateur."""

    serializer_class = MembreSerializer
    pagination_class = None
    district_field = "district"

    def get_queryset(self):
        profil = profil_de(self.request.user)
        if not profil or profil.role != R.ADMIN:
            raise PermissionDenied("La gestion des comptes est réservée à l'administrateur.")
        # Les comptes des fidèles (rôle MEMBRE) se gèrent depuis la page « Accès des membres »
        return (Profil.objects.filter(organisation_id=profil.organisation_id).exclude(role=R.MEMBRE)
                .select_related("user", "district").order_by("user__username"))

    def perform_create(self, serializer):
        self.get_queryset()
        self._verifier_district(serializer)
        instance = serializer.save(organisation=profil_de(self.request.user).organisation)
        self._journaliser("CREATION", instance)

    def perform_update(self, serializer):
        if serializer.instance.user_id == self.request.user.id and serializer.validated_data.get("role", R.ADMIN) != R.ADMIN:
            raise PermissionDenied("Vous ne pouvez pas retirer votre propre rôle d'administrateur.")
        u = serializer.validated_data.get("user", {})
        mdp_change = bool(serializer.validated_data.get("mot_de_passe"))
        super().perform_update(serializer)
        # Compte désactivé ou mot de passe changé par l'administrateur : ses sessions ouvertes sont fermées
        if u.get("is_active") is False or mdp_change:
            revoquer_tout(serializer.instance.user)


@api_view(["GET", "PATCH"])
def mon_organisation(request):
    profil = profil_de(request.user)
    org = profil.organisation
    if request.method == "PATCH":
        if profil.role != R.ADMIN:
            raise PermissionDenied("Seul l'administrateur peut modifier les paramètres.")
        s = OrganisationSerializer(org, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)
    return Response(OrganisationSerializer(org).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])  # personnel et membres de l'Église
def moi(request):
    p = profil_de(request.user)
    if p is None:
        raise PermissionDenied("Ce compte n'est rattaché à aucune organisation.")
    org = p.organisation
    fiche = None
    if p.est_membre_simple:
        f = getattr(request.user, "fiche_membre", None)
        if f is not None:
            fiche = {"id": f.id, "numero": f.numero, "paroisse": f.paroisse_id, "paroisse_nom": f.paroisse.nom}
    return Response({
        "est_membre": p.est_membre_simple,
        "doit_changer_mdp": p.doit_changer_mdp,
        "fiche": fiche,
        "username": request.user.username,
        "nom": request.user.get_full_name() or request.user.username,
        "role": p.role,
        "role_libelle": p.get_role_display(),
        "district": p.district_id,
        "district_nom": p.district.nom if p.district else None,
        "voit_tout": p.voit_tout,
        "totp_actif": p.totp_actif,
        "organisation": OrganisationSerializer(org).data if org else None,
        "version": __import__("config.version", fromlist=["VERSION"]).VERSION,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def changer_mot_de_passe(request):
    """Chaque utilisateur change son mot de passe (obligatoire après un mot de passe provisoire)."""
    ancien, nouveau = request.data.get("ancien", ""), request.data.get("nouveau", "")
    if not request.user.check_password(ancien):
        raise ValidationError({"ancien": "Le mot de passe actuel est incorrect."})
    if ancien == nouveau:
        raise ValidationError({"nouveau": "Choisissez un mot de passe différent de l'actuel."})
    try:
        validate_password(nouveau, request.user)
    except ErreurDjango as e:
        raise ValidationError({"nouveau": list(e.messages)})
    request.user.set_password(nouveau)
    request.user.save(update_fields=["password"])
    p = profil_de(request.user)
    if p and p.doit_changer_mdp:
        p.doit_changer_mdp = False
        p.save(update_fields=["doit_changer_mdp"])
    JournalAction.objects.create(organisation_id=p.organisation_id if p else None, utilisateur=request.user,
                                 action="MODIFICATION", objet_type="Compte", objet_id=str(request.user.pk),
                                 objet_libelle=request.user.username, details={"mot_de_passe": "changé par l'utilisateur"})
    # Toutes les autres sessions (autres appareils, jeton volé) sont fermées ; celle-ci repart sur un jeton neuf
    revoquer_tout(request.user)
    return nouvelle_session(request.user, Response({"ok": True}))


class InscriptionThrottle(AnonRateThrottle):
    rate = "5/hour"


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([InscriptionThrottle])
def inscription(request):
    """Une nouvelle Église ou organisation crée son espace sans intervention extérieure."""
    s = InscriptionSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    org = s.save()
    return Response({"slug": org.slug, "nom": org.nom, "identifiant": request.data["admin_identifiant"]}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([AllowAny])
def organisations_publiques(request):
    """Liste des organisations qui publient un portail de transparence."""
    return Response(list(Organisation.objects.filter(portail_public=True).exclude(statut="SUSPENDU").values("slug", "nom", "sigle", "pays")))


@api_view(["GET"])
@permission_classes([AllowAny])
def sante(request):
    """Supervision : à interroger toutes les 5 minutes (UptimeRobot, Uptime Kuma...). Aucune donnée sensible."""
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    from metier.taches import derniere_execution

    from config.version import VERSION

    from django.conf import settings

    etat = {"version": VERSION, "demo": settings.UMURAGE_DEMO, "base": False, "migrations_en_attente": None,
            "taches": derniere_execution()}
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        etat["base"] = True
        ex = MigrationExecutor(connection)
        etat["migrations_en_attente"] = len(ex.migration_plan(ex.loader.graph.leaf_nodes()))
    except Exception as e:  # la page de santé ne doit jamais planter
        etat["erreur"] = type(e).__name__
    etat["ok"] = etat["base"] and etat["migrations_en_attente"] == 0
    return Response(etat, status=200 if etat["ok"] else 503)


@api_view(["GET"])
def diagnostic_adresse_ip(request):
    """
    Aide au réglage de UMURAGE_NUM_PROXIES (administrateur) : montre l'adresse retenue pour les limites
    de tentatives à côté de ce que reçoit le serveur. Elle doit être l'adresse publique de votre appareil.
    """
    from django.conf import settings
    from rest_framework.throttling import BaseThrottle

    profil = profil_de(request.user)
    if profil.role != R.ADMIN:
        raise PermissionDenied("Réservé à l'administrateur.")
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    retenue = BaseThrottle().get_ident(request)
    conseil = None
    if xff and settings.NUM_PROXIES == 0:
        conseil = ("Un proxy transmet X-Forwarded-For mais UMURAGE_NUM_PROXIES vaut 0 : tous les visiteurs partagent "
                   "l'adresse du proxy. Mettez UMURAGE_NUM_PROXIES=1 (ou le nombre de proxys en chaîne).")
    elif not xff and settings.NUM_PROXIES > 0:
        conseil = ("UMURAGE_NUM_PROXIES est supérieur à 0 mais aucun proxy n'ajoute X-Forwarded-For : remettez 0, "
                   "ou configurez le proxy pour qu'il ajoute cet en-tête.")
    return Response({
        "adresse_retenue": retenue, "num_proxies": settings.NUM_PROXIES,
        "remote_addr": request.META.get("REMOTE_ADDR"), "x_forwarded_for": xff or None,
        "conseil": conseil or "Réglage cohérent : vérifiez que l'adresse retenue est bien l'adresse publique de votre appareil.",
    })
