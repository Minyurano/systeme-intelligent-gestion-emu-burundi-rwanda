"""
Fichiers téléversés protégés (titres fonciers, contrats, photos des membres et des biens, photos et vocaux
des déclarations).

Jusqu'à la 3.8, Django servait le dossier media/ à n'importe qui, sans connexion : il suffisait de connaître
l'adresse d'un titre foncier ou de la photo d'un fidèle pour l'ouvrir. Depuis la 3.9 :

1. L'API ne renvoie plus l'adresse brute d'un fichier, mais un **lien signé et temporaire** :
   « /media/documents/titre.pdf?j=... ». La signature (clé secrète du serveur) contient le chemin du fichier,
   le compte qui l'a reçu et l'heure d'émission. Elle ne peut être ni fabriquée ni modifiée.
   Le lien n'est remis qu'à quelqu'un qui a le droit de voir la fiche, puisqu'il est produit dans la réponse
   de l'API, déjà limitée à son organisation, son district et son rôle.
2. Le lien expire (4 heures par défaut, `FICHIERS_LIEN_MINUTES`) et cesse de fonctionner si le compte
   est désactivé.
3. Sans signature, un client API peut encore demander le fichier avec son en-tête « Authorization: Bearer » :
   on vérifie alors que la fiche correspondante est bien dans son périmètre.
4. Un fichier HTML, SVG ou autre format actif est toujours téléchargé, jamais affiché : un fichier piégé
   ne peut pas exécuter de script dans la page.

Un lien signé fonctionne dans <img>, <audio> ou un nouvel onglet, alors que le jeton d'accès (gardé en mémoire
par l'application) ne peut pas y être joint.
"""
import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.http import FileResponse, Http404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny

SEL = "umurage.fichiers"
AFFICHABLES = {"application/pdf", "image/jpeg", "image/png", "image/gif", "image/webp", "text/plain"}


def duree_lien():
    return int(getattr(settings, "FICHIERS_LIEN_MINUTES", 240)) * 60


def url_signee(fichier, user, request=None):
    """Lien temporaire vers un fichier, réservé au compte `user`. None si pas de fichier ou pas de compte."""
    if not fichier or not getattr(fichier, "name", None) or not (user and user.is_authenticated):
        return None
    jeton = signing.dumps({"c": fichier.name, "u": user.pk}, salt=SEL, compress=True)
    chemin = f"/{settings.MEDIA_URL.strip('/')}/{fichier.name}?j={jeton}"
    return request.build_absolute_uri(chemin) if request is not None else chemin


class _Signe:
    """Remplace l'adresse brute d'un fichier par un lien signé dans toutes les réponses de l'API."""

    def to_representation(self, value):
        requete = self.context.get("request")
        return url_signee(value, getattr(requete, "user", None), requete)


class ChampFichierSigne(_Signe, serializers.FileField):
    pass


class ChampImageSigne(_Signe, serializers.ImageField):
    pass


def installer():
    """Appelé au démarrage (core.apps) : tous les ModelSerializer utilisent les champs signés."""
    from django.db import models
    from rest_framework.serializers import ModelSerializer

    ModelSerializer.serializer_field_mapping[models.FileField] = ChampFichierSigne
    ModelSerializer.serializer_field_mapping[models.ImageField] = ChampImageSigne


# ------------------------------------------------------------------------------- Accès sans signature
def _cibles():
    from metier.views import MembreEgliseViewSet
    from patrimoine.declarations import DeclarationViewSet
    from patrimoine.views import BienViewSet, DocumentViewSet

    return {
        "documents": (DocumentViewSet, "fichier"),
        "biens": (BienViewSet, "photo"),
        "membres": (MembreEgliseViewSet, "photo"),
        "declarations": (DeclarationViewSet, "media"),
    }


def _visible(request, vue_classe, champ, chemin):
    """Même périmètre que la liste correspondante de l'API (organisation, district, rôle)."""
    vue = vue_classe()
    vue.request = request
    vue.args, vue.kwargs, vue.format_kwarg, vue.action = (), {}, None, "retrieve"
    if not all(p.has_permission(request, vue) for p in vue.get_permissions()):
        return False
    return vue.get_queryset().filter(**{champ: chemin}).exists()


def _signature_valide(jeton, chemin):
    try:
        donnees = signing.loads(jeton, salt=SEL, max_age=duree_lien())
    except signing.BadSignature:  # signature falsifiée ou lien expiré
        return False
    if donnees.get("c") != chemin:
        return False
    return get_user_model().objects.filter(pk=donnees.get("u"), is_active=True).exists()


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def fichier_protege(request, chemin):
    chemin = chemin.lstrip("/")
    racine = Path(settings.MEDIA_ROOT).resolve()
    fichier = (racine / chemin).resolve()
    if racine not in fichier.parents or not fichier.is_file():
        raise Http404

    jeton = request.query_params.get("j")
    if jeton:
        autorise = _signature_valide(jeton, chemin)
    elif request.user and request.user.is_authenticated:
        cible = _cibles().get(chemin.split("/", 1)[0])
        autorise = cible is not None and _visible(request, *cible, chemin)
    else:
        autorise = False
    if not autorise:
        raise Http404  # 404 plutôt que 403 : on ne confirme pas qu'un fichier existe

    type_mime, _ = mimetypes.guess_type(fichier.name)
    reponse = FileResponse(open(fichier, "rb"), content_type=type_mime or "application/octet-stream")
    if (type_mime or "") not in AFFICHABLES and not (type_mime or "").startswith(("audio/", "video/")):
        reponse["Content-Disposition"] = f'attachment; filename="{fichier.name}"'
    reponse["Cache-Control"] = "private, max-age=3600"
    reponse["X-Content-Type-Options"] = "nosniff"
    reponse["Referrer-Policy"] = "no-referrer"
    return reponse
