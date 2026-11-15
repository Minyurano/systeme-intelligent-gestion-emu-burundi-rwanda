"""
Saisie par WhatsApp : un pasteur ou un agent envoie un message, une photo ou un message
vocal ; UMURAGE comprend le message, crée une déclaration à valider et répond.

Connexion à l'API WhatsApp Cloud de Meta (facultative) :
  WHATSAPP_TOKEN          jeton d'accès permanent de l'application Meta
  WHATSAPP_PHONE_ID       identifiant du numéro WhatsApp Business
  WHATSAPP_VERIFY_TOKEN   mot secret choisi pour vérifier le webhook
Sans ces variables, tout fonctionne quand même avec le simulateur intégré à l'application
(les réponses sont simplement affichées au lieu d'être envoyées).
"""
import json
import logging
import os
import re
import tempfile
import urllib.request

from django.core.files.base import ContentFile

from core.models import Profil

from .comprehension import COMMANDES_AIDE, interpreter, normaliser, resumer
from .models import Bien, Declaration

log = logging.getLogger("umurage.whatsapp")
GRAPH = "https://graph.facebook.com/v20.0"

AIDE = (
    "UMURAGE — déclarer un bien de l'Église\n"
    "• Décrivez le bien en une phrase : « Nouveau forage à Muyange, en bon état, financé par UMCOR ».\n"
    "• Ajoutez une photo ou un message vocal si vous le souhaitez.\n"
    "• Pour connaître l'état d'un bien : ETAT suivi de son code, par exemple ETAT BRG-INF-0001.\n"
    "Votre déclaration sera vérifiée par votre surintendant avant d'entrer dans l'inventaire."
)


def numero(n):
    """Garde les chiffres, pour comparer +257 79 00 00 01 et 25779000001."""
    return re.sub(r"\D", "", n or "")


def trouver_profil(expediteur):
    cible = numero(expediteur)
    if not cible:
        return None
    # Pré-filtre en base sur les derniers chiffres : les comptes des membres rendent la table volumineuse
    candidats = Profil.objects.filter(telephone__endswith=cible[-6:]).select_related("organisation", "district", "user")
    for p in candidats:
        if numero(p.telephone) == cible and p.user.is_active:
            return p
    return None


def transcrire(contenu, extension=".ogg"):
    """Transcrit un message vocal si faster-whisper est installé (fonctionne en kirundi, français, swahili...)."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return ""
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as f:
        f.write(contenu)
    modele = WhisperModel(os.environ.get("WHISPER_MODELE", "small"), device="cpu", compute_type="int8")
    segments, _ = modele.transcribe(f.name)
    return " ".join(s.text.strip() for s in segments)


def traiter_message(expediteur, texte="", media=None, canal=Declaration.Canal.WHATSAPP):
    """
    Point d'entrée commun (webhook WhatsApp, SMS, simulateur).
    `media` : dict facultatif {"contenu": bytes, "type": "image"|"audio", "nom": "x.jpg"}.
    Renvoie (déclaration ou None, texte de la réponse).
    """
    profil = trouver_profil(expediteur)
    if profil is None:
        return None, ("Ce numéro n'est pas enregistré dans UMURAGE. Demandez à l'administrateur de votre "
                      "Église d'ajouter votre numéro de téléphone à votre compte.")
    return traiter_message_profil(profil, expediteur, texte, media, canal)


def traiter_message_profil(profil, expediteur, texte="", media=None, canal=Declaration.Canal.WHATSAPP, bien=None):
    """
    Même traitement pour un auteur déjà identifié (WhatsApp, ou espace membre de l'application).
    `bien` : bien choisi directement par l'auteur (signalement sur un bien existant).
    """
    org = profil.organisation
    brut = (texte or "").strip()
    t = normaliser(brut)

    if t in COMMANDES_AIDE:
        return None, AIDE

    m = re.match(r"^(etat|state)\s+([a-z0-9-]+)$", t)
    if m:
        b = Bien.objects.filter(district__organisation=org, code__iexact=m.group(2)).first()
        if not b:
            return None, f"Aucun bien ne porte le code {m.group(2).upper()}."
        risque = f", risque {round(b.score_risque)}/100" if b.score_risque is not None else ""
        return None, f"{b.code} — {b.nom} : {b.get_etat_display().lower()}{risque}."

    transcription = ""
    if media and media.get("type") == "audio":
        transcription = transcrire(media["contenu"], os.path.splitext(media.get("nom", ".ogg"))[1] or ".ogg")
    a_comprendre = " ".join(x for x in (brut, transcription) if x)
    if not a_comprendre and not media:
        return None, AIDE

    interp = interpreter(a_comprendre, org, profil.district) if a_comprendre else {"manquants": ["la description du bien"], "confiance": 0}
    district_id = interp.pop("district", None) or profil.district_id
    if not profil.voit_tout and profil.district_id and district_id != profil.district_id:
        # Un agent ne déclare que dans son district : un lieu situé ailleurs est écarté
        district_id = profil.district_id
        if interp.get("paroisse"):
            interp["manquants"] = interp.get("manquants", []) + [f"le lieu ({interp['paroisse_nom']} n'est pas dans votre district)"]
            interp.update(paroisse=None, paroisse_nom=None, bien_existant=None)

    if bien is not None:
        # L'auteur a désigné le bien lui-même : pas besoin de le deviner
        interp["bien_existant"] = {"id": bien.id, "code": bien.code, "nom": bien.nom, "etat": bien.etat}
        district_id = bien.district_id

    d = Declaration(
        organisation=org, district_id=district_id, canal=canal, expediteur=expediteur, auteur=profil.user,
        auteur_nom=profil.user.get_full_name() or profil.user.username,
        texte=brut, transcription=transcription, interpretation=interp,
    )
    if media:
        d.media_type = media.get("type", "")
        d.media.save(media.get("nom", "media.bin"), ContentFile(media["contenu"]), save=False)
    d.save()

    if interp.get("bien_existant"):
        ex = interp["bien_existant"]
        return d, (f"Merci ! Signalement n° {d.pk} reçu pour {ex['code']} — {ex['nom']}. "
                   "Votre surintendant va mettre à jour sa fiche.")
    reponse = f"Merci ! Déclaration n° {d.pk} reçue : {resumer(interp, org.devise)}." if interp.get("nom") else f"Merci ! Déclaration n° {d.pk} reçue."
    if interp.get("manquants"):
        reponse += " Il manque : " + ", ".join(interp["manquants"]) + ". Vous pouvez répondre pour compléter."
    reponse += " Elle sera vérifiée par votre surintendant."
    return d, reponse


# ------------------------------------------------------------------ API WhatsApp Cloud (Meta)

def _requete(url, corps=None):
    jeton = os.environ.get("WHATSAPP_TOKEN")
    if not jeton:
        return None
    req = urllib.request.Request(url, data=json.dumps(corps).encode() if corps else None,
                                 headers={"Authorization": f"Bearer {jeton}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def configure():
    """Vrai si l'API WhatsApp Cloud est branchée (sinon les messages sont seulement journalisés)."""
    return bool(os.environ.get("WHATSAPP_PHONE_ID") and os.environ.get("WHATSAPP_TOKEN"))


def envoyer(destinataire, texte):
    """Répond sur WhatsApp. Sans configuration, la réponse est seulement journalisée."""
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")
    if not (phone_id and os.environ.get("WHATSAPP_TOKEN")):
        log.info("Réponse WhatsApp (non envoyée, API non configurée) à %s : %s", destinataire, texte)
        return False
    try:
        _requete(f"{GRAPH}/{phone_id}/messages", {
            "messaging_product": "whatsapp", "to": numero(destinataire), "type": "text", "text": {"body": texte[:4000]},
        })
        return True
    except Exception as e:  # une panne d'envoi ne doit jamais perdre la déclaration
        log.warning("Échec d'envoi WhatsApp : %s", e)
        return False


def telecharger_media(media_id):
    """Récupère une photo ou un message vocal envoyé sur WhatsApp."""
    try:
        info = json.loads(_requete(f"{GRAPH}/{media_id}") or b"{}")
        if not info.get("url"):
            return None
        return {"contenu": _requete(info["url"]), "mime": info.get("mime_type", "")}
    except Exception as e:
        log.warning("Média WhatsApp illisible : %s", e)
        return None


def messages_du_webhook(charge):
    """Extrait les messages d'une notification WhatsApp Cloud API."""
    for entree in charge.get("entry", []):
        for changement in entree.get("changes", []):
            for msg in changement.get("value", {}).get("messages", []):
                yield msg
