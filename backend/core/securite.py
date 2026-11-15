"""
Règles d'accès, cloisonnement entre organisations et journal d'audit.

Deux niveaux de cloisonnement s'appliquent à chaque requête :
1. Organisation : un utilisateur ne voit jamais les données d'une autre organisation.
2. District : un surintendant ou un agent ne voit que son district.
"""
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied

from .models import JournalAction, Organisation, Profil

R = Profil.Role


def profil_de(user):
    if not user or not user.is_authenticated:
        return None
    profil = getattr(user, "profil", None)
    if profil is None and user.is_superuser:
        profil, _ = Profil.objects.get_or_create(
            user=user, defaults={"role": R.ADMIN, "organisation": Organisation.objects.order_by("id").first()}
        )
    return profil


def _organisation_active(profil):
    return profil is not None and profil.organisation_id is not None and profil.organisation.statut != Organisation.Statut.SUSPENDU


class EstPersonnel(permissions.BasePermission):
    """
    Permission par défaut de toute l'API : réservée au personnel de l'organisation
    (administrateur, direction, trésorier, surintendant, agent).

    Un simple membre de l'Église (rôle MEMBRE) est refusé partout, sauf sur les adresses
    qui l'autorisent explicitement (espace membre, profil, mot de passe, double authentification).
    Ainsi, une nouvelle page de gestion ajoutée plus tard est fermée aux fidèles par défaut.
    """

    message = "Cette partie de UMURAGE est réservée aux responsables de l'Église."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        profil = profil_de(request.user)
        return _organisation_active(profil) and not profil.est_membre_simple


class EstMembre(permissions.BasePermission):
    """Espace membre : uniquement les fidèles dont l'accès a été donné par un administrateur."""

    message = "L'espace membre est réservé aux membres de l'Église."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        profil = profil_de(request.user)
        return _organisation_active(profil) and profil.est_membre_simple


class RolePermission(permissions.BasePermission):
    """
    Lecture : tout responsable connecté de l'organisation (le périmètre est limité par DistrictScopedMixin).
    Écriture : seulement les rôles listés dans `roles_ecriture` de la vue.
    Les simples membres (rôle MEMBRE) n'y ont jamais accès.
    """

    message = EstPersonnel.message

    def has_permission(self, request, view):
        profil = profil_de(request.user)
        if not _organisation_active(profil) or profil.est_membre_simple:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return profil.role in getattr(view, "roles_ecriture", (R.ADMIN,))

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        profil = profil_de(request.user)
        district = _suivre(obj, getattr(view, "district_field", "district"))
        if district is not None and district.organisation_id != profil.organisation_id:
            return False
        if profil.voit_tout:
            return True
        return district is not None and district.pk == profil.district_id


def _suivre(obj, chemin):
    """Suit un chemin « bien__district » sur un objet."""
    cible = obj
    for part in chemin.split("__"):
        cible = getattr(cible, part, None)
        if cible is None:
            return None
    return cible


def _organisation_de(obj):
    """Organisation d'un objet du modèle (directement, via son district ou via son bien)."""
    if not hasattr(obj, "_meta"):
        return None
    for chemin in ("organisation_id", "district.organisation_id", "bien.district.organisation_id", "projet.district.organisation_id"):
        cible = obj
        for part in chemin.split("."):
            cible = getattr(cible, part, None)
            if cible is None:
                break
        if cible is not None:
            return cible
    return None


class DistrictScopedMixin:
    """Limite chaque liste à l'organisation de l'utilisateur, puis à son district s'il n'a pas une vue globale."""

    district_field = "district"
    permission_classes = [RolePermission]

    def get_queryset(self):
        qs = super().get_queryset()
        profil = profil_de(self.request.user)
        if profil is None:
            return qs.none()
        qs = qs.filter(**{f"{self.district_field}__organisation_id": profil.organisation_id})
        if not profil.voit_tout:
            if profil.district_id is None:
                return qs.none()
            qs = qs.filter(**{self.district_field: profil.district_id})
        return qs


class OrganisationScopedMixin:
    """Pour les objets rattachés directement à une organisation (districts, documents)."""

    permission_classes = [RolePermission]

    def get_queryset(self):
        profil = profil_de(self.request.user)
        if profil is None:
            return super().get_queryset().none()
        return super().get_queryset().filter(organisation_id=profil.organisation_id)


class JournalMixin:
    """Contrôle le district écrit et enregistre chaque écriture dans le journal d'audit."""

    def _journaliser(self, action, instance, details=None):
        profil = profil_de(self.request.user)
        JournalAction.objects.create(
            organisation_id=profil.organisation_id if profil else None,
            utilisateur=self.request.user if self.request.user.is_authenticated else None,
            action=action,
            objet_type=instance._meta.verbose_name.title(),
            objet_id=str(instance.pk),
            objet_libelle=str(instance)[:255],
            details=details or {},
        )

    def _verifier_district(self, serializer):
        """On n'écrit jamais dans une autre organisation, ni (sauf vue globale) dans un autre district."""
        profil = profil_de(self.request.user)
        # Aucune référence (bien, projet, paroisse, district...) ne peut pointer vers une autre organisation
        for valeur in serializer.validated_data.values():
            org = _organisation_de(valeur)
            if org is not None and org != profil.organisation_id:
                raise PermissionDenied("Cette référence n'appartient pas à votre organisation.")
        champ = getattr(self, "district_field", "district").split("__")
        valeur = serializer.validated_data.get(champ[0])
        for part in champ[1:]:
            valeur = getattr(valeur, part, None) if valeur is not None else None
        if valeur is None:
            return
        if getattr(valeur, "organisation_id", profil.organisation_id) != profil.organisation_id:
            raise PermissionDenied("Ce district n'appartient pas à votre organisation.")
        if not profil.voit_tout and valeur.pk != profil.district_id:
            raise PermissionDenied("Vous ne pouvez enregistrer que des données de votre district.")

    def perform_create(self, serializer):
        self._verifier_district(serializer)
        instance = serializer.save()
        self._journaliser("CREATION", instance)

    def perform_update(self, serializer):
        self._verifier_district(serializer)
        avant = {k: str(getattr(serializer.instance, k, "")) for k in serializer.validated_data}
        instance = serializer.save()
        changements = {
            k: {"avant": avant[k], "apres": str(getattr(instance, k, ""))}
            for k in avant
            if avant[k] != str(getattr(instance, k, ""))
        }
        self._journaliser("MODIFICATION", instance, changements)

    def perform_destroy(self, instance):
        self._journaliser("SUPPRESSION", instance)
        instance.delete()
