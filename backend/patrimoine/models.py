from datetime import date

from django.conf import settings
from django.db import models

from core.models import District, Organisation, Paroisse

ODD_LIBELLES = {
    "2": "ODD 2 — Faim zéro",
    "3": "ODD 3 — Santé et bien-être",
    "4": "ODD 4 — Éducation de qualité",
    "5": "ODD 5 — Égalité entre les sexes",
    "6": "ODD 6 — Eau propre",
    "10": "ODD 10 — Inégalités réduites",
}


class Bien(models.Model):
    """Un élément du patrimoine : terrain, bâtiment, forage, équipement, cheptel..."""

    class Categorie(models.TextChoices):
        FONCIER = "FON", "Foncier (terrain)"
        IMMOBILIER = "IMM", "Immobilier (bâtiment)"
        INFRASTRUCTURE = "INF", "Infrastructure (forage, usine...)"
        EQUIPEMENT = "EQP", "Équipement / matériel"
        VEHICULE = "VEH", "Véhicule"
        AGRICOLE = "AGR", "Agricole et élevage"

    class Etat(models.TextChoices):
        BON = "BON", "Bon"
        MOYEN = "MOYEN", "Moyen"
        MAUVAIS = "MAUVAIS", "Mauvais"
        CONSTRUCTION = "CONSTRUCTION", "En construction"

    class Juridique(models.TextChoices):
        TITRE = "TITRE", "Titre de propriété"
        EN_COURS = "EN_COURS", "Démarches en cours"
        SANS_TITRE = "SANS_TITRE", "Sans titre"
        NA = "NA", "Non applicable"

    # Unique au sein d'une organisation (deux organisations peuvent utiliser les mêmes codes de district)
    code = models.CharField(max_length=20, db_index=True, editable=False)
    nom = models.CharField(max_length=160)
    categorie = models.CharField(max_length=3, choices=Categorie.choices)
    sous_type = models.CharField(max_length=80, blank=True, help_text="ex. école, centre de santé, forage, porcherie")
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="biens")
    paroisse = models.ForeignKey(Paroisse, null=True, blank=True, on_delete=models.SET_NULL, related_name="biens")
    description = models.TextField(blank=True)
    etat = models.CharField(max_length=15, choices=Etat.choices, default=Etat.BON)
    statut_juridique = models.CharField(max_length=12, choices=Juridique.choices, default=Juridique.NA)
    surface_m2 = models.FloatField(null=True, blank=True)
    quantite = models.PositiveIntegerField(default=1)
    date_acquisition = models.DateField(null=True, blank=True)
    valeur_acquisition = models.DecimalField(max_digits=16, decimal_places=0, default=0, help_text="En francs burundais (BIF)")
    valeur_estimee = models.DecimalField(max_digits=16, decimal_places=0, null=True, blank=True)
    methode_valorisation = models.CharField(max_length=40, blank=True)
    duree_vie_ans = models.PositiveIntegerField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    financeur = models.CharField(max_length=120, blank=True)
    odd = models.CharField(max_length=30, blank=True, help_text="Numéros d'ODD séparés par des virgules, ex. 3,6")
    beneficiaires = models.PositiveIntegerField(default=0)
    responsable = models.CharField(max_length=120, blank=True)
    photo = models.ImageField(upload_to="biens/", null=True, blank=True)
    score_risque = models.FloatField(null=True, blank=True)
    # Renseignée quand le bien quitte le patrimoine (cession approuvée) : il sort de l'inventaire actif
    date_sortie = models.DateField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        # Index pour les tableaux de bord, filtres et cartes (requêtes par district, catégorie, état, risque)
        indexes = [
            models.Index(fields=["district", "categorie"], name="bien_district_categorie"),
            models.Index(fields=["district", "etat"], name="bien_district_etat"),
            models.Index(fields=["score_risque"], name="bien_score_risque"),
        ]
        verbose_name = "bien"

    def __str__(self):
        return f"{self.code} — {self.nom}"

    def save(self, *args, **kwargs):
        if not self.code:
            prefixe = f"{self.district.code}-{self.categorie}-"
            dernier = (
                Bien.objects.filter(district__organisation_id=self.district.organisation_id, code__startswith=prefixe)
                .order_by("-code").values_list("code", flat=True).first()
            )
            numero = int(dernier.rsplit("-", 1)[1]) + 1 if dernier else 1
            self.code = f"{prefixe}{numero:04d}"
        super().save(*args, **kwargs)

    @property
    def age_ans(self):
        if not self.date_acquisition:
            return None
        return round((date.today() - self.date_acquisition).days / 365.25, 1)

    @property
    def valeur_courante(self):
        return self.valeur_estimee if self.valeur_estimee is not None else self.valeur_acquisition


class Mouvement(models.Model):
    """Historique d'un bien : acquisition, maintenance, inspection, transfert, cession."""

    class Type(models.TextChoices):
        ACQUISITION = "ACQUISITION", "Acquisition"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        REPARATION = "REPARATION", "Réparation"
        INSPECTION = "INSPECTION", "Inspection"
        TRANSFERT = "TRANSFERT", "Transfert"
        CESSION = "CESSION", "Cession"

    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="mouvements")
    type = models.CharField(max_length=15, choices=Type.choices)
    date = models.DateField()
    montant = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    description = models.TextField(blank=True)
    auteur = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["-date"]
        indexes = [models.Index(fields=["bien", "-date"], name="mouvement_bien_date")]
        verbose_name = "mouvement"

    def __str__(self):
        return f"{self.get_type_display()} — {self.bien.code} ({self.date})"


class Document(models.Model):
    """Archive numérisée : titre foncier, contrat, rapport, convention..."""

    class Type(models.TextChoices):
        TITRE_FONCIER = "TITRE_FONCIER", "Titre foncier"
        CONTRAT = "CONTRAT", "Contrat"
        RAPPORT = "RAPPORT", "Rapport"
        CONVENTION = "CONVENTION", "Convention"
        FACTURE = "FACTURE", "Facture"
        CARTE_GRISE = "CARTE_GRISE", "Carte grise"
        ASSURANCE = "ASSURANCE", "Attestation d'assurance"
        PV = "PV", "Procès-verbal"
        AUTRE = "AUTRE", "Autre"

    titre = models.CharField(max_length=200)
    organisation = models.ForeignKey(Organisation, null=True, on_delete=models.CASCADE, related_name="documents")
    type = models.CharField(max_length=15, choices=Type.choices, default=Type.AUTRE)
    bien = models.ForeignKey(Bien, null=True, blank=True, on_delete=models.SET_NULL, related_name="documents")
    district = models.ForeignKey(District, null=True, blank=True, on_delete=models.SET_NULL)
    fichier = models.FileField(upload_to="documents/", null=True, blank=True)
    contenu = models.TextField(blank=True, help_text="Texte extrait (saisi ou obtenu par OCR), utilisé par l'assistant")
    date = models.DateField(null=True, blank=True)
    date_expiration = models.DateField(null=True, blank=True, help_text="Assurance, carte grise, permis... : un rappel est créé")
    version = models.PositiveSmallIntegerField(default=1)
    remplace = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="versions_suivantes")
    transaction = models.ForeignKey("finances.Transaction", null=True, blank=True, on_delete=models.SET_NULL, related_name="pieces",
                                    help_text="Pièce justificative d'une transaction")
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "titre"]
        verbose_name = "document"

    def __str__(self):
        return self.titre


class Projet(models.Model):
    """Projet de développement ou de construction suivi pour son impact."""

    class Domaine(models.TextChoices):
        SANTE = "SANTE", "Santé"
        EDUCATION = "EDUCATION", "Éducation"
        EAU = "EAU", "Eau potable"
        AGRICULTURE = "AGRICULTURE", "Agriculture et élevage"
        FEMMES = "FEMMES", "Autonomisation des femmes"
        HUMANITAIRE = "HUMANITAIRE", "Humanitaire"
        INCLUSION = "INCLUSION", "Inclusion"

    class Statut(models.TextChoices):
        PREVU = "PREVU", "Prévu"
        EN_COURS = "EN_COURS", "En cours"
        TERMINE = "TERMINE", "Terminé"
        SUSPENDU = "SUSPENDU", "Suspendu"

    nom = models.CharField(max_length=180)
    domaine = models.CharField(max_length=15, choices=Domaine.choices)
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="projets")
    bien = models.ForeignKey(Bien, null=True, blank=True, on_delete=models.SET_NULL, related_name="projets")
    description = models.TextField(blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EN_COURS)
    avancement = models.PositiveIntegerField(default=0, help_text="Pourcentage 0-100")
    budget = models.DecimalField(max_digits=16, decimal_places=0, default=0)
    depense = models.DecimalField(max_digits=16, decimal_places=0, default=0)
    financeur = models.CharField(max_length=120, blank=True)
    odd = models.CharField(max_length=30, blank=True)
    beneficiaires = models.PositiveIntegerField(default=0)
    date_debut = models.DateField(null=True, blank=True)
    date_fin_prevue = models.DateField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    public = models.BooleanField(default=True, help_text="Visible sur le portail public de transparence")

    class Meta:
        ordering = ["district__nom", "nom"]
        verbose_name = "projet"

    def __str__(self):
        return self.nom


class Declaration(models.Model):
    """
    Bien signalé depuis le terrain (WhatsApp, SMS, application hors-ligne) et en attente de validation.
    Rien n'entre dans l'inventaire officiel sans la validation d'un responsable.
    """

    class Canal(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"
        SMS = "SMS", "SMS"
        WEB = "WEB", "Application"

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        VALIDEE = "VALIDEE", "Validée"
        REJETEE = "REJETEE", "Rejetée"

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="declarations")
    district = models.ForeignKey(District, null=True, blank=True, on_delete=models.SET_NULL)
    canal = models.CharField(max_length=10, choices=Canal.choices, default=Canal.WHATSAPP)
    expediteur = models.CharField(max_length=30, help_text="Numéro de téléphone de l'auteur")
    auteur_nom = models.CharField(max_length=120, blank=True)
    # Compte de l'auteur (permet à un membre de suivre ses signalements depuis son espace)
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="declarations")
    texte = models.TextField(blank=True)
    transcription = models.TextField(blank=True, help_text="Texte obtenu à partir d'un message vocal")
    media = models.FileField(upload_to="declarations/", null=True, blank=True)
    media_type = models.CharField(max_length=20, blank=True)
    interpretation = models.JSONField(default=dict, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    bien = models.ForeignKey(Bien, null=True, blank=True, on_delete=models.SET_NULL, related_name="declarations")
    motif_rejet = models.CharField(max_length=255, blank=True)
    traitee_par = models.CharField(max_length=120, blank=True)
    recue_le = models.DateTimeField(auto_now_add=True)
    traitee_le = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["statut", "-recue_le"]
        indexes = [models.Index(fields=["organisation", "statut", "-recue_le"], name="declaration_org_statut")]
        verbose_name = "déclaration"

    def __str__(self):
        return f"Déclaration {self.pk} de {self.auteur_nom or self.expediteur}"
