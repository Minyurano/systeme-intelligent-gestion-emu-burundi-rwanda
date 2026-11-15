from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import District
from patrimoine.models import Projet


class Transaction(models.Model):
    """Recette ou dépense. Analysée par le module de détection d'anomalies."""

    class Sens(models.TextChoices):
        RECETTE = "RECETTE", "Recette"
        DEPENSE = "DEPENSE", "Dépense"

    class Categorie(models.TextChoices):
        DIME = "DIME", "Dîmes et offrandes"
        DON = "DON", "Don"
        SUBVENTION = "SUBVENTION", "Subvention partenaire"
        REVENU_PROJET = "REVENU_PROJET", "Revenu de projet"
        SALAIRE = "SALAIRE", "Salaires"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        CONSTRUCTION = "CONSTRUCTION", "Construction"
        FONCTIONNEMENT = "FONCTIONNEMENT", "Fonctionnement"
        ACHAT = "ACHAT", "Achat de matériel"
        LOYER = "LOYER", "Loyers perçus"
        CESSION = "CESSION", "Produit de cession"

    class Canal(models.TextChoices):
        BANQUE = "BANQUE", "Banque"
        ESPECES = "ESPECES", "Espèces"
        MOBILE = "MOBILE", "Mobile Money"

    date = models.DateField()
    sens = models.CharField(max_length=8, choices=Sens.choices)
    categorie = models.CharField(max_length=15, choices=Categorie.choices)
    montant = models.DecimalField(max_digits=16, decimal_places=2)
    devise = models.CharField(max_length=3, default="BIF", help_text="Monnaie locale de l'organisation ou USD")
    montant_bif = models.DecimalField(max_digits=18, decimal_places=0, editable=False, default=0)
    canal = models.CharField(max_length=8, choices=Canal.choices, default=Canal.BANQUE)
    reference_externe = models.CharField(max_length=60, blank=True, help_text="ex. référence Lumicash / EcoCash")
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="transactions")
    projet = models.ForeignKey(Projet, null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions")
    tiers = models.CharField(max_length=120, blank=True, help_text="Bénéficiaire ou donateur")
    description = models.CharField(max_length=255, blank=True)
    score_anomalie = models.FloatField(null=True, blank=True)
    est_anomalie = models.BooleanField(default=False)
    motifs_anomalie = models.JSONField(default=list, blank=True)
    verifiee = models.BooleanField(default=False, help_text="Contrôlée par le trésorier")
    rapprochee = models.BooleanField(default=False, help_text="Retrouvée sur le relevé bancaire ou Mobile Money")
    bien = models.ForeignKey("patrimoine.Bien", null=True, blank=True, on_delete=models.SET_NULL, related_name="transactions")

    class Meta:
        ordering = ["-date", "-id"]
        # Index pour les tendances mensuelles, les totaux par sens et la liste des anomalies
        indexes = [
            models.Index(fields=["district", "date"], name="transaction_district_date"),
            models.Index(fields=["district", "sens"], name="transaction_district_sens"),
            models.Index(fields=["est_anomalie", "verifiee"], name="transaction_anomalie"),
        ]
        verbose_name = "transaction"

    def __str__(self):
        return f"{self.date} {self.get_sens_display()} {self.montant} {self.devise}"

    def save(self, *args, **kwargs):
        # Conversion en monnaie locale de l'organisation (le champ garde son nom historique montant_bif)
        org = self.district.organisation if self.district_id else None
        taux = Decimal(str(org.taux_usd if org else settings.UMURAGE["TAUX_USD_BIF"]))
        self.montant_bif = (self.montant * taux) if self.devise == "USD" else self.montant
        super().save(*args, **kwargs)
