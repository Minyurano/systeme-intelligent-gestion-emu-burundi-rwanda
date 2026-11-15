"""
Mot de passe oublié, en libre-service.

1. La personne saisit son identifiant (ou son numéro de membre).
2. Un code à 6 chiffres est envoyé sur WhatsApp (numéro du compte) et/ou par e-mail.
3. Elle saisit le code et choisit un nouveau mot de passe ; toutes ses sessions ouvertes sont fermées.

Protections : réponse identique que le compte existe ou non ; seule l'empreinte du code est gardée ;
10 minutes de validité ; 5 essais par code ; 5 demandes par heure et par adresse IP ; la double
authentification reste exigée à la connexion suivante.
"""
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErreurDjango
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .jetons import revoquer_tout
from .models import CodeReinitialisation, JournalAction

log = logging.getLogger("umurage.securite")
VALIDITE = timedelta(minutes=10)
ESSAIS_MAX = 5
REPONSE = ("Si ce compte existe et qu'un numéro WhatsApp ou une adresse e-mail y est enregistré, un code à 6 chiffres "
           "vient d'y être envoyé. Il est valable 10 minutes. Sans réception, demandez à l'administrateur de votre Église.")


class MdpOublieThrottle(AnonRateThrottle):
    # AnonRateThrottle (et non ScopedRateThrottle, qui lit la portée sur la vue et laissait tout passer) :
    # compteur par adresse IP réelle, voir UMURAGE_NUM_PROXIES.
    scope = "mdp_oublie"


class CodeThrottle(AnonRateThrottle):
    """Saisie du code : compteur séparé (chaque code n'accepte de toute façon que 5 essais)."""
    scope = "mdp_code"


def empreinte(code, user_id):
    return hmac.new(settings.SECRET_KEY.encode(), f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


def trouver_compte(identifiant):
    identifiant = (identifiant or "").strip()
    if not identifiant:
        return None
    comptes = list(User.objects.filter(username__iexact=identifiant, is_active=True)[:2])
    return comptes[0] if len(comptes) == 1 else None


def envoyer_code(user, code):
    """Envoie le code sur les canaux disponibles ; renvoie la liste des canaux utilisés."""
    from patrimoine import whatsapp

    canaux = []
    profil = getattr(user, "profil", None)
    texte = (f"UMURAGE — votre code pour choisir un nouveau mot de passe : {code}\n"
             "Valable 10 minutes. Ne le communiquez à personne, même à un responsable de l'Église.")
    if profil and profil.telephone and whatsapp.configure() and whatsapp.envoyer(profil.telephone, texte):
        canaux.append("WhatsApp")
    if user.email:
        try:
            send_mail("UMURAGE — code de réinitialisation", texte, None, [user.email], fail_silently=False)
            canaux.append("e-mail")
        except Exception as e:  # serveur de messagerie absent : on n'interrompt pas la demande
            log.warning("Envoi du code par e-mail impossible : %s", e)
    return canaux


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([MdpOublieThrottle])
def demander_code(request):
    user = trouver_compte(request.data.get("identifiant"))
    if user is not None:
        code = f"{secrets.randbelow(1_000_000):06d}"
        with transaction.atomic():
            CodeReinitialisation.objects.filter(user=user, utilise=False).update(utilise=True)  # un seul code valable
            c = CodeReinitialisation.objects.create(user=user, empreinte=empreinte(code, user.pk), expire_le=timezone.now() + VALIDITE)
        c.canaux = ", ".join(envoyer_code(user, code))
        c.save(update_fields=["canaux"])
        if not c.canaux:
            log.info("Mot de passe oublié : aucun canal d'envoi pour le compte %s", user.pk)
    return Response({"ok": True, "message": REPONSE})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([CodeThrottle])
def reinitialiser(request):
    erreur = ValidationError({"code": "Code incorrect ou expiré. Demandez un nouveau code."})
    user = trouver_compte(request.data.get("identifiant"))
    saisi = "".join(ch for ch in str(request.data.get("code") or "") if ch.isdigit())
    nouveau = request.data.get("nouveau") or ""
    if user is None or len(saisi) != 6:
        raise erreur
    try:
        validate_password(nouveau, user)
    except ErreurDjango as e:
        raise ValidationError({"nouveau": list(e.messages)})  # vérifié avant : un mot de passe refusé ne coûte pas un essai
    with transaction.atomic():
        c = (CodeReinitialisation.objects.select_for_update()
             .filter(user=user, utilise=False, expire_le__gt=timezone.now()).order_by("-cree_le").first())
        if c is None:
            raise erreur
        c.essais += 1
        bon = hmac.compare_digest(c.empreinte, empreinte(saisi, user.pk))
        c.utilise = bon or c.essais >= ESSAIS_MAX
        c.save(update_fields=["essais", "utilise"])  # l'essai est compté et enregistré avant toute réponse
        if bon:
            user.set_password(nouveau)
            user.save(update_fields=["password"])
            profil = getattr(user, "profil", None)
            if profil and profil.doit_changer_mdp:
                profil.doit_changer_mdp = False
                profil.save(update_fields=["doit_changer_mdp"])
            revoquer_tout(user)
            JournalAction.objects.create(organisation_id=getattr(profil, "organisation_id", None), utilisateur=user,
                                         action="MODIFICATION", objet_type="Compte", objet_id=str(user.pk), objet_libelle=user.username,
                                         details={"mot_de_passe": "réinitialisé par code", "canaux": c.canaux})
    if not bon:
        reste = ESSAIS_MAX - c.essais
        raise ValidationError({"code": f"Code incorrect. {reste} essai(s) restant(s)." if reste > 0 else erreur.detail["code"]})
    return Response({"ok": True, "message": "Mot de passe changé. Vous pouvez vous connecter."})
