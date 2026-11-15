from django.utils import timezone

from .models import Alerte, Capteur, Mesure


def enregistrer_mesure(capteur: Capteur, valeur: float, horodatage=None, verifier_alertes=True):
    """Enregistre une mesure, met à jour le capteur et déclenche une alerte si un seuil est franchi."""
    horodatage = horodatage or timezone.now()
    mesure = Mesure.objects.create(capteur=capteur, valeur=valeur, horodatage=horodatage)
    if capteur.derniere_mesure is None or horodatage >= capteur.derniere_mesure:
        capteur.derniere_valeur = valeur
        capteur.derniere_mesure = horodatage
        capteur.save(update_fields=["derniere_valeur", "derniere_mesure"])
    if verifier_alertes:
        verifier_seuils(capteur, valeur)
    return mesure


def verifier_seuils(capteur: Capteur, valeur: float):
    message = None
    if capteur.seuil_min is not None and valeur < capteur.seuil_min:
        message = f"{capteur.get_type_display()} trop bas : {valeur:.1f} {capteur.unite} (min {capteur.seuil_min})"
    elif capteur.seuil_max is not None and valeur > capteur.seuil_max:
        message = f"{capteur.get_type_display()} trop élevé : {valeur:.1f} {capteur.unite} (max {capteur.seuil_max})"
    if not message:
        return None
    # Une seule alerte ouverte par capteur, pour ne pas inonder les responsables
    if Alerte.objects.filter(capteur=capteur, resolue=False).exists():
        return None
    niveau = Alerte.Niveau.CRITIQUE if capteur.type == Capteur.Type.TEMPERATURE else Alerte.Niveau.ATTENTION
    return Alerte.objects.create(
        capteur=capteur, bien=capteur.bien, niveau=niveau, message=f"{capteur.bien.nom} — {message}"
    )
