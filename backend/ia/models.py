from django.db import models

from core.models import District


class ComparableMarche(models.Model):
    """
    Transaction immobilière ou foncière de référence observée sur le marché local.
    Sert de données d'entraînement au modèle de valorisation.
    """

    categorie = models.CharField(max_length=3)  # FON ou IMM
    district = models.ForeignKey(District, on_delete=models.CASCADE)
    surface_m2 = models.FloatField()
    age_ans = models.FloatField(default=0)
    etat = models.CharField(max_length=15, default="BON")
    distance_ville_km = models.FloatField(default=5)
    prix_bif = models.DecimalField(max_digits=16, decimal_places=0)
    date = models.DateField()
    source = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-date"]


class EntrainementModele(models.Model):
    """Trace de chaque entraînement d'un modèle (MLOps léger)."""

    modele = models.CharField(max_length=40)
    date = models.DateTimeField(auto_now_add=True)
    nb_exemples = models.PositiveIntegerField()
    metriques = models.JSONField(default=dict)

    class Meta:
        ordering = ["-date"]
