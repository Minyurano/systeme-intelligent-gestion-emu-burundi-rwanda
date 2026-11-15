"""
Jetons de connexion à l'abri du JavaScript de la page.

- Le jeton de rafraîchissement (7 jours) vit dans un cookie HttpOnly, SameSite=Strict, limité à /api/auth/ :
  un script injecté dans la page (faille XSS) ne peut pas le lire, et un autre site ne peut pas l'envoyer.
- Le jeton d'accès (15 minutes) est renvoyé dans la réponse et gardé en mémoire par l'application, jamais
  dans le stockage du navigateur. À chaque ouverture, l'application en redemande un avec le cookie.
- Chaque rafraîchissement remplace le cookie et révoque l'ancien jeton (rotation + liste noire) :
  un jeton volé et réutilisé est refusé.
- `revoquer_tout(user)` ferme toutes les sessions d'un compte (mot de passe changé, accès suspendu…).
"""
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

COOKIE = "umurage_refresh"
CHEMIN = "/api/auth/"
ENTETE = "HTTP_X_UMURAGE"  # en-tête X-Umurage : un autre site ne peut pas l'ajouter sans autorisation CORS


def poser_cookie(reponse, refresh):
    reponse.set_cookie(
        COOKIE, str(refresh), max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=CHEMIN, httponly=True, secure=not settings.DEBUG, samesite="Strict",
    )
    return reponse


def effacer_cookie(reponse):
    reponse.delete_cookie(COOKIE, path=CHEMIN, samesite="Strict")
    return reponse


def deplacer_refresh_dans_cookie(reponse):
    """Réponse de connexion : le jeton de rafraîchissement quitte le corps pour le cookie."""
    if reponse.status_code == 200 and isinstance(reponse.data, dict) and "refresh" in reponse.data:
        refresh = reponse.data.pop("refresh")
        poser_cookie(reponse, refresh)
    return reponse


def nouvelle_session(user, reponse):
    """Ouvre une session neuve (après un changement de mot de passe par exemple)."""
    refresh = RefreshToken.for_user(user)
    reponse.data["access"] = str(refresh.access_token)
    return poser_cookie(reponse, refresh)


def revoquer_tout(user):
    """Met sur liste noire tous les jetons de rafraîchissement encore valides du compte."""
    from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

    for jeton in OutstandingToken.objects.filter(user=user).exclude(blacklistedtoken__isnull=False):
        BlacklistedToken.objects.get_or_create(token=jeton)


class RafraichirThrottle(AnonRateThrottle):
    # AnonRateThrottle (et non ScopedRateThrottle, qui lit la portée sur la vue et laissait tout passer) :
    # compteur par adresse IP réelle, voir UMURAGE_NUM_PROXIES.
    scope = "rafraichir"


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([RafraichirThrottle])
def rafraichir(request):
    """Nouveau jeton d'accès à partir du cookie (ou du champ `refresh` pour les clients hors navigateur)."""
    brut = request.data.get("refresh") if isinstance(request.data, dict) else None
    par_cookie = not brut
    if par_cookie:
        brut = request.COOKIES.get(COOKIE)
        if brut and not request.META.get(ENTETE):
            return Response({"detail": "En-tête X-Umurage manquant."}, status=status.HTTP_403_FORBIDDEN)
    if not brut:
        return Response({"detail": "Aucune session."}, status=status.HTTP_401_UNAUTHORIZED)
    s = TokenRefreshSerializer(data={"refresh": brut})
    try:
        s.is_valid(raise_exception=True)
    except Exception:  # jeton expiré, révoqué, compte supprimé ou désactivé
        return effacer_cookie(Response({"detail": "Session expirée. Reconnectez-vous."}, status=status.HTTP_401_UNAUTHORIZED))
    donnees = dict(s.validated_data)
    nouveau = donnees.pop("refresh", None)
    reponse = Response(donnees if par_cookie else {**donnees, **({"refresh": nouveau} if nouveau else {})})
    if par_cookie and nouveau:
        poser_cookie(reponse, nouveau)
    return reponse


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def deconnexion(request):
    """Révoque le jeton de rafraîchissement de cet appareil et efface le cookie."""
    brut = request.COOKIES.get(COOKIE) or (request.data.get("refresh") if isinstance(request.data, dict) else None)
    if brut:
        try:
            RefreshToken(brut).blacklist()
        except TokenError:
            pass
    return effacer_cookie(Response(status=status.HTTP_204_NO_CONTENT))
