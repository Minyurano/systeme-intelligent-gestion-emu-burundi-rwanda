from django.db import models

from patrimoine.models import Bien


class Capteur(models.Model):
    """Capteur connecté (ESP32 + LoRaWAN/MQTT) installé sur un bien."""

    class Type(models.TextChoices):
        NIVEAU_EAU = "NIVEAU_EAU", "Niveau d'eau"
        DEBIT = "DEBIT", "Débit"
        TEMPERATURE = "TEMPERATURE", "Température (chaîne du froid)"
        ENERGIE = "ENERGIE", "Énergie"

    code = models.CharField(max_length=30, unique=True)
    type = models.CharField(max_length=12, choices=Type.choices)
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="capteurs")
    unite = models.CharField(max_length=10)
    seuil_min = models.FloatField(null=True, blank=True)
    seuil_max = models.FloatField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    derniere_valeur = models.FloatField(null=True, blank=True)
    derniere_mesure = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "capteur"

    def __str__(self):
        return f"{self.code} ({self.get_type_display()})"


class Mesure(models.Model):
    capteur = models.ForeignKey(Capteur, on_delete=models.CASCADE, related_name="mesures")
    horodatage = models.DateTimeField(db_index=True)
    valeur = models.FloatField()

    class Meta:
        ordering = ["-horodatage"]
        indexes = [models.Index(fields=["capteur", "-horodatage"])]


class Alerte(models.Model):
    class Niveau(models.TextChoices):
        INFO = "INFO", "Information"
        ATTENTION = "ATTENTION", "Attention"
        CRITIQUE = "CRITIQUE", "Critique"

    capteur = models.ForeignKey(Capteur, null=True, blank=True, on_delete=models.CASCADE, related_name="alertes")
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="alertes")
    niveau = models.CharField(max_length=10, choices=Niveau.choices)
    message = models.CharField(max_length=255)
    date = models.DateTimeField(auto_now_add=True)
    resolue = models.BooleanField(default=False)

    class Meta:
        ordering = ["resolue", "-date"]
        indexes = [models.Index(fields=["bien", "resolue"], name="alerte_bien_resolue")]
        verbose_name = "alerte"

    def __str__(self):
        return self.message
