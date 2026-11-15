"""
Double authentification (TOTP, RFC 6238) pour les comptes sensibles : évêque, trésorier, administrateur.

Compatible avec Google Authenticator, Microsoft Authenticator, FreeOTP... Implémentation sans dépendance externe.
"""
import base64
import hashlib
import hmac
import io
import secrets
import struct
import time
from urllib.parse import quote

import qrcode
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.throttling import ScopedRateThrottle

from .securite import profil_de

PAS = 30


def nouveau_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def code_totp(secret, instant=None):
    cle = base64.b32decode(secret + "=" * (-len(secret) % 8))
    compteur = int((instant if instant is not None else time.time()) // PAS)
    h = hmac.new(cle, struct.pack(">Q", compteur), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    return f"{(struct.unpack('>I', h[o:o + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}"


def verifier(secret, code, fenetre=1):
    """Accepte le code de la période courante et de ±30 secondes (décalage d'horloge du téléphone)."""
    code = "".join(c for c in str(code or "") if c.isdigit())
    if not secret or len(code) != 6:
        return False
    t = time.time()
    return any(hmac.compare_digest(code_totp(secret, t + d * PAS), code) for d in range(-fenetre, fenetre + 1))


class ConnexionSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # Identifiant insensible à la casse : « git-2026-00012 » ouvre le compte « GIT-2026-00012 »
        from django.contrib.auth.models import User
        saisi = attrs.get(self.username_field, "")
        if saisi and not User.objects.filter(username=saisi).exists():
            trouve = User.objects.filter(username__iexact=saisi.strip()).values_list("username", flat=True)
            if len(trouve) == 1:
                attrs[self.username_field] = trouve[0]
        donnees = super().validate(attrs)
        profil = getattr(self.user, "profil", None)
        if profil and profil.totp_actif:
            code = self.initial_data.get("code")
            if not code:
                raise AuthenticationFailed({"detail": "Saisissez le code à 6 chiffres de votre application d'authentification.", "otp_requis": True})
            if not verifier(profil.totp_secret, code):
                raise AuthenticationFailed({"detail": "Code de vérification incorrect.", "otp_requis": True})
        return donnees


class Connexion(TokenObtainPairView):
    """Connexion limitée à 10 tentatives par minute, avec double authentification si elle est activée."""

    serializer_class = ConnexionSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "connexion"

    def post(self, request, *args, **kwargs):
        from .jetons import deplacer_refresh_dans_cookie
        # Le jeton de rafraîchissement part dans un cookie HttpOnly, hors de portée du JavaScript
        return deplacer_refresh_dans_cookie(super().post(request, *args, **kwargs))


@api_view(["POST"])
@permission_classes([IsAuthenticated])  # aussi pour les membres de l'Église
def activer(request):
    """Étape 1 : génère un secret et le QR code à scanner. La double authentification n'est active qu'après confirmation."""
    profil = profil_de(request.user)
    profil.totp_secret = nouveau_secret()
    profil.totp_actif = False
    profil.save(update_fields=["totp_secret", "totp_actif"])
    org = profil.organisation.sigle if profil.organisation else "UMURAGE"
    uri = f"otpauth://totp/{quote('UMURAGE')}:{quote(request.user.username)}?secret={profil.totp_secret}&issuer={quote('UMURAGE ' + org)}"
    img = qrcode.make(uri)
    tampon = io.BytesIO()
    img.save(tampon, format="PNG")
    return Response({"secret": profil.totp_secret, "uri": uri, "qr": "data:image/png;base64," + base64.b64encode(tampon.getvalue()).decode()})


@api_view(["POST"])
@permission_classes([IsAuthenticated])  # aussi pour les membres de l'Église
def confirmer(request):
    profil = profil_de(request.user)
    if not verifier(profil.totp_secret, request.data.get("code")):
        raise ValidationError({"code": "Code incorrect. Vérifiez l'heure du téléphone et réessayez."})
    profil.totp_actif = True
    profil.save(update_fields=["totp_actif"])
    return Response({"totp_actif": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])  # aussi pour les membres de l'Église
def desactiver(request):
    profil = profil_de(request.user)
    if profil.totp_actif and not verifier(profil.totp_secret, request.data.get("code")):
        raise ValidationError({"code": "Code incorrect."})
    profil.totp_actif, profil.totp_secret = False, ""
    profil.save(update_fields=["totp_actif", "totp_secret"])
    return Response({"totp_actif": False})
