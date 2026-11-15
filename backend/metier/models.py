"""
Modules métier d'UMURAGE : ce qui transforme l'inventaire en outil de gestion quotidienne.

1. Circuits d'approbation (Demande, Avis)
2. Échéancier et rappels (Echeance)
3. Baux et loyers (Bail, Loyer)
4. Maintenance (Fournisseur, PlanMaintenance, OrdreTravail)
5. Comptabilité du patrimoine (Budget, ClotureExercice ; le registre des immobilisations est calculé)
6. Campagnes d'inventaire physique (Campagne, Constat)
7. Registre officiel des membres (MembreEglise)
"""
import calendar
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction

from core.models import District, Organisation, Paroisse, Profil, Verrou
from finances.models import Transaction
from patrimoine.models import Bien

R = Profil.Role


def ajouter_mois(d, n):
    """Même jour n mois plus tard (ramené au dernier jour du mois si besoin)."""
    m = d.month - 1 + n
    annee, mois = d.year + m // 12, m % 12 + 1
    return date(annee, mois, min(d.day, calendar.monthrange(annee, mois)[1]))


# ====================================================================== 1. Circuits d'approbation
class Demande(models.Model):
    """
    Une décision qui engage le patrimoine : elle passe par plusieurs niveaux de validation
    avant d'être exécutée. Celui qui demande ne valide jamais sa propre demande.
    """

    class Type(models.TextChoices):
        ACQUISITION = "ACQUISITION", "Acquisition d'un bien"
        CESSION = "CESSION", "Cession (vente, don) d'un bien"
        TRANSFERT = "TRANSFERT", "Transfert vers un autre district"
        TRAVAUX = "TRAVAUX", "Travaux importants"
        DEPENSE = "DEPENSE", "Dépense"

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente de validation"
        APPROUVEE = "APPROUVEE", "Approuvée, à exécuter"
        REJETEE = "REJETEE", "Rejetée"
        EXECUTEE = "EXECUTEE", "Exécutée"
        ANNULEE = "ANNULEE", "Annulée"

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="demandes")
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="demandes")
    type = models.CharField(max_length=12, choices=Type.choices)
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    bien = models.ForeignKey(Bien, null=True, blank=True, on_delete=models.SET_NULL, related_name="demandes")
    district_destination = models.ForeignKey(District, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    montant = models.DecimalField(max_digits=16, decimal_places=0, default=0)
    categorie_depense = models.CharField(max_length=15, choices=Transaction.Categorie.choices, blank=True)
    demandeur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="demandes")
    circuit = models.JSONField(default=list, help_text="Rôles qui valident, dans l'ordre")
    niveau = models.PositiveSmallIntegerField(default=0, help_text="Index du niveau en cours dans le circuit")
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    cree_le = models.DateTimeField(auto_now_add=True)
    decide_le = models.DateTimeField(null=True, blank=True)
    execute_le = models.DateTimeField(null=True, blank=True)
    resultat = models.CharField(max_length=255, blank=True, help_text="Ce que l'exécution a produit")

    class Meta:
        ordering = ["-cree_le"]
        indexes = [models.Index(fields=["organisation", "statut"], name="demande_org_statut")]
        verbose_name = "demande"

    def __str__(self):
        return f"{self.get_type_display()} — {self.titre}"

    @property
    def role_attendu(self):
        if self.statut != self.Statut.EN_ATTENTE or self.niveau >= len(self.circuit):
            return None
        return self.circuit[self.niveau]


class Avis(models.Model):
    class Decision(models.TextChoices):
        APPROUVE = "APPROUVE", "Approuvé"
        REJETE = "REJETE", "Rejeté"

    demande = models.ForeignKey(Demande, on_delete=models.CASCADE, related_name="avis")
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    role = models.CharField(max_length=20, choices=R.choices)
    niveau = models.PositiveSmallIntegerField()
    decision = models.CharField(max_length=10, choices=Decision.choices)
    commentaire = models.TextField(blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]
        verbose_name = "avis"


# ====================================================================== 2. Échéancier
class Echeance(models.Model):
    """Une date à ne pas manquer. Les rappels partent automatiquement 30 et 7 jours avant."""

    class Type(models.TextChoices):
        ASSURANCE = "ASSURANCE", "Assurance"
        IMPOT = "IMPOT", "Impôt foncier / taxe"
        TITRE = "TITRE", "Titre de propriété"
        CONTROLE_TECHNIQUE = "CONTROLE", "Contrôle technique"
        FIN_BAIL = "FIN_BAIL", "Fin de bail"
        MAINTENANCE = "MAINTENANCE", "Maintenance prévue"
        DOCUMENT = "DOCUMENT", "Document qui expire"
        AUTRE = "AUTRE", "Autre"

    class Statut(models.TextChoices):
        A_FAIRE = "A_FAIRE", "À faire"
        FAIT = "FAIT", "Fait"

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="echeances")
    district = models.ForeignKey(District, null=True, blank=True, on_delete=models.CASCADE, related_name="echeances")
    bien = models.ForeignKey(Bien, null=True, blank=True, on_delete=models.CASCADE, related_name="echeances")
    type = models.CharField(max_length=12, choices=Type.choices, default=Type.AUTRE)
    libelle = models.CharField(max_length=200)
    date = models.DateField()
    periodicite_mois = models.PositiveSmallIntegerField(default=0, help_text="0 = une seule fois ; 12 = chaque année")
    montant = models.DecimalField(max_digits=16, decimal_places=0, default=0)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    statut = models.CharField(max_length=8, choices=Statut.choices, default=Statut.A_FAIRE)
    fait_le = models.DateField(null=True, blank=True)
    rappel_j30 = models.BooleanField(default=False)
    rappel_j7 = models.BooleanField(default=False)
    rappel_retard = models.BooleanField(default=False)
    origine = models.CharField(max_length=40, blank=True, help_text="Génération automatique, ex. bail:12, document:5")

    class Meta:
        ordering = ["statut", "date"]
        indexes = [models.Index(fields=["organisation", "statut", "date"], name="echeance_org_statut_date")]
        verbose_name = "échéance"

    def __str__(self):
        return f"{self.libelle} ({self.date})"


# ====================================================================== 3. Baux et loyers
class Bail(models.Model):
    class Statut(models.TextChoices):
        ACTIF = "ACTIF", "En cours"
        TERMINE = "TERMINE", "Terminé"

    bien = models.ForeignKey(Bien, on_delete=models.PROTECT, related_name="baux")
    locataire = models.CharField(max_length=160)
    telephone = models.CharField(max_length=30, blank=True)
    objet = models.CharField(max_length=200, blank=True, help_text="ex. boutique n°3, salle de réception")
    loyer_mensuel = models.DecimalField(max_digits=14, decimal_places=0)
    caution = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    jour_echeance = models.PositiveSmallIntegerField(default=5, help_text="Jour du mois où le loyer est dû")
    statut = models.CharField(max_length=8, choices=Statut.choices, default=Statut.ACTIF)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["statut", "bien__code"]
        verbose_name = "bail"
        verbose_name_plural = "baux"

    def __str__(self):
        return f"{self.locataire} — {self.bien.nom}"

    def generer_loyers(self, jusqu_a=None):
        """Crée les loyers mensuels dus, du début du bail jusqu'au mois de jusqu_a (aujourd'hui par défaut)."""
        jusqu_a = jusqu_a or date.today()
        fin = min(self.date_fin, jusqu_a) if self.date_fin else jusqu_a
        periode = self.date_debut.replace(day=1)
        crees = 0
        while periode <= fin:
            jour = min(self.jour_echeance, calendar.monthrange(periode.year, periode.month)[1])
            _, cree = Loyer.objects.get_or_create(
                bail=self, periode=periode,
                defaults={"echeance": periode.replace(day=jour), "montant_du": self.loyer_mensuel},
            )
            crees += cree
            periode = ajouter_mois(periode, 1)
        return crees


class Loyer(models.Model):
    bail = models.ForeignKey(Bail, on_delete=models.CASCADE, related_name="loyers")
    periode = models.DateField(help_text="Premier jour du mois concerné")
    echeance = models.DateField()
    montant_du = models.DecimalField(max_digits=14, decimal_places=0)
    montant_paye = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    paye_le = models.DateField(null=True, blank=True)
    transaction = models.ForeignKey(Transaction, null=True, blank=True, on_delete=models.SET_NULL, related_name="loyers")

    class Meta:
        ordering = ["-periode"]
        unique_together = ("bail", "periode")
        verbose_name = "loyer"

    @property
    def reste(self):
        return max(Decimal(0), self.montant_du - self.montant_paye)

    @property
    def statut(self):
        if self.reste == 0:
            return "PAYE"
        if self.echeance < date.today():
            return "IMPAYE" if self.montant_paye == 0 else "PARTIEL"
        return "A_VENIR"


# ====================================================================== 4. Maintenance
class Fournisseur(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="fournisseurs")
    nom = models.CharField(max_length=160)
    specialite = models.CharField(max_length=120, blank=True, help_text="ex. forages, électricité, toiture, mécanique")
    telephone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["nom"]
        verbose_name = "fournisseur"

    def __str__(self):
        return self.nom


class PlanMaintenance(models.Model):
    """Entretien préventif : un ordre de travail est créé automatiquement à chaque échéance."""

    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="plans_maintenance")
    libelle = models.CharField(max_length=200)
    periodicite_mois = models.PositiveSmallIntegerField(default=6)
    prochaine_date = models.DateField()
    fournisseur = models.ForeignKey(Fournisseur, null=True, blank=True, on_delete=models.SET_NULL)
    cout_estime = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["prochaine_date"]
        verbose_name = "plan de maintenance"

    def __str__(self):
        return f"{self.libelle} — {self.bien.nom}"


class OrdreTravail(models.Model):
    class Type(models.TextChoices):
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        REPARATION = "REPARATION", "Réparation"
        INSPECTION = "INSPECTION", "Inspection"

    class Priorite(models.TextChoices):
        BASSE = "BASSE", "Basse"
        NORMALE = "NORMALE", "Normale"
        HAUTE = "HAUTE", "Haute"
        URGENTE = "URGENTE", "Urgente"

    class Statut(models.TextChoices):
        DEMANDE = "DEMANDE", "Demandé"
        PLANIFIE = "PLANIFIE", "Planifié"
        EN_COURS = "EN_COURS", "En cours"
        TERMINE = "TERMINE", "Terminé"
        ANNULE = "ANNULE", "Annulé"

    class Origine(models.TextChoices):
        MANUEL = "MANUEL", "Saisie"
        PLAN = "PLAN", "Plan préventif"
        RISQUE = "RISQUE", "Risque détecté par l'IA"
        DEMANDE = "DEMANDE", "Demande approuvée"
        INVENTAIRE = "INVENTAIRE", "Campagne d'inventaire"

    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="ordres_travail")
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=12, choices=Type.choices, default=Type.REPARATION)
    priorite = models.CharField(max_length=8, choices=Priorite.choices, default=Priorite.NORMALE)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.DEMANDE)
    origine = models.CharField(max_length=10, choices=Origine.choices, default=Origine.MANUEL)
    fournisseur = models.ForeignKey(Fournisseur, null=True, blank=True, on_delete=models.SET_NULL, related_name="ordres")
    cout_estime = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    cout_reel = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    date_prevue = models.DateField(null=True, blank=True)
    termine_le = models.DateField(null=True, blank=True)
    rapport = models.TextField(blank=True, help_text="Ce qui a été fait")
    plan = models.ForeignKey(PlanMaintenance, null=True, blank=True, on_delete=models.SET_NULL, related_name="ordres")
    demande = models.ForeignKey(Demande, null=True, blank=True, on_delete=models.SET_NULL, related_name="ordres")
    transaction = models.ForeignKey(Transaction, null=True, blank=True, on_delete=models.SET_NULL, related_name="ordres_travail")
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["statut", "-cree_le"]
        indexes = [models.Index(fields=["bien", "statut"], name="ordre_bien_statut")]
        verbose_name = "ordre de travail"
        verbose_name_plural = "ordres de travail"

    def __str__(self):
        return f"OT-{self.pk} {self.titre}"

    OUVERTS = (Statut.DEMANDE, Statut.PLANIFIE, Statut.EN_COURS)


# ====================================================================== 5. Comptabilité du patrimoine
class Budget(models.Model):
    """Une ligne de budget annuel, à comparer avec les transactions réelles."""

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="budgets")
    annee = models.PositiveSmallIntegerField()
    district = models.ForeignKey(District, null=True, blank=True, on_delete=models.CASCADE, help_text="Vide = toute l'organisation")
    projet = models.ForeignKey("patrimoine.Projet", null=True, blank=True, on_delete=models.CASCADE, related_name="lignes_budget")
    sens = models.CharField(max_length=8, choices=Transaction.Sens.choices)
    categorie = models.CharField(max_length=15, choices=Transaction.Categorie.choices)
    montant = models.DecimalField(max_digits=16, decimal_places=0)

    class Meta:
        ordering = ["annee", "sens", "categorie"]
        verbose_name = "ligne de budget"


class ClotureExercice(models.Model):
    """Une fois l'exercice clôturé, plus aucune transaction de cette année ne peut être créée, modifiée ou supprimée."""

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="clotures")
    annee = models.PositiveSmallIntegerField()
    cloture_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    date = models.DateTimeField(auto_now_add=True)
    totaux = models.JSONField(default=dict, help_text="Photographie des totaux au moment de la clôture")

    class Meta:
        unique_together = ("organisation", "annee")
        ordering = ["-annee"]
        verbose_name = "clôture d'exercice"


# ====================================================================== 6. Campagnes d'inventaire physique
class Campagne(models.Model):
    class Statut(models.TextChoices):
        OUVERTE = "OUVERTE", "En cours"
        CLOTUREE = "CLOTUREE", "Clôturée"

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="campagnes")
    district = models.ForeignKey(District, null=True, blank=True, on_delete=models.CASCADE, help_text="Vide = toute l'organisation")
    nom = models.CharField(max_length=160)
    date_debut = models.DateField(default=date.today)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.OUVERTE)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    cloturee_le = models.DateTimeField(null=True, blank=True)
    proces_verbal = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-date_debut"]
        verbose_name = "campagne d'inventaire"

    def __str__(self):
        return self.nom


class Constat(models.Model):
    campagne = models.ForeignKey(Campagne, on_delete=models.CASCADE, related_name="constats")
    bien = models.ForeignKey(Bien, on_delete=models.CASCADE, related_name="constats")
    trouve = models.BooleanField(default=True)
    etat_constate = models.CharField(max_length=15, choices=Bien.Etat.choices, blank=True)
    commentaire = models.CharField(max_length=255, blank=True)
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    date = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("campagne", "bien")
        ordering = ["-date"]
        verbose_name = "constat"


# ====================================================================== 7. Registre des membres
class MembreEglise(models.Model):
    """
    Fiche officielle d'un membre, rattachée à une église locale (paroisse).
    Le numéro de membre est attribué une seule fois et ne change jamais : DISTRICT-ANNÉE-NNNNN.
    """

    class Sexe(models.TextChoices):
        HOMME = "H", "Homme"
        FEMME = "F", "Femme"

    class Statut(models.TextChoices):
        SYMPATHISANT = "SYMPATHISANT", "Sympathisant"
        CATECHUMENE = "CATECHUMENE", "Catéchumène"
        BAPTISE = "BAPTISE", "Membre baptisé"
        CONFESSANT = "CONFESSANT", "Membre confessant"
        TRANSFERE = "TRANSFERE", "Transféré"
        DECEDE = "DECEDE", "Décédé"

    class Situation(models.TextChoices):
        CELIBATAIRE = "CELIBATAIRE", "Célibataire"
        MARIE = "MARIE", "Marié(e)"
        VEUF = "VEUF", "Veuf / veuve"
        DIVORCE = "DIVORCE", "Divorcé(e)"

    ACTIFS = (Statut.SYMPATHISANT, Statut.CATECHUMENE, Statut.BAPTISE, Statut.CONFESSANT)

    numero = models.CharField(max_length=24, unique=True, editable=False)
    paroisse = models.ForeignKey(Paroisse, on_delete=models.PROTECT, related_name="registre")
    nom = models.CharField(max_length=80)
    prenom = models.CharField(max_length=80)
    sexe = models.CharField(max_length=1, choices=Sexe.choices)
    date_naissance = models.DateField(null=True, blank=True)
    lieu_naissance = models.CharField(max_length=120, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    adresse = models.CharField(max_length=160, blank=True, help_text="Colline, quartier ou commune")
    situation_familiale = models.CharField(max_length=12, choices=Situation.choices, blank=True)
    profession = models.CharField(max_length=120, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.CATECHUMENE)
    date_adhesion = models.DateField(default=date.today)
    date_bapteme = models.DateField(null=True, blank=True)
    date_confirmation = models.DateField(null=True, blank=True)
    ministere = models.CharField(max_length=120, blank=True, help_text="Chorale, Femmes, Jeunesse, école du dimanche…")
    photo = models.ImageField(upload_to="membres/", null=True, blank=True)
    notes = models.TextField(blank=True)
    enregistre_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    # Accord d'un parent ou tuteur, exigé pour ouvrir l'accès d'un membre plus jeune que l'âge fixé par l'organisation
    accord_parental_nom = models.CharField(max_length=120, blank=True)
    accord_parental_lien = models.CharField(max_length=40, blank=True, help_text="Père, mère, tuteur…")
    accord_parental_le = models.DateField(null=True, blank=True)
    accord_parental_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    # Compte de l'espace membre, créé par un administrateur (vide = pas d'accès en ligne)
    compte = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="fiche_membre")
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nom", "prenom"]
        verbose_name = "membre de l'Église"
        verbose_name_plural = "registre des membres"
        indexes = [models.Index(fields=["paroisse", "statut"]), models.Index(fields=["nom", "prenom"])]

    def __str__(self):
        return f"{self.numero} — {self.prenom} {self.nom}"

    @property
    def actif(self):
        return self.statut in self.ACTIFS

    def age(self, le=None):
        if not self.date_naissance:
            return None
        j = le or date.today()
        n = self.date_naissance
        return j.year - n.year - ((j.month, j.day) < (n.month, n.day))

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.numero:
                self.numero = self._prochain_numero()
            super().save(*args, **kwargs)
        self.synchroniser_compte()

    def _prochain_numero(self):
        """
        DISTRICT-ANNÉE-NNNNN, attribué sous verrou : deux agents qui enregistrent au même moment
        reçoivent deux numéros différents au lieu d'une erreur d'unicité.
        """
        prefixe = f"{self.paroisse.district.code}-{date.today().year}-"

        def plus_grand_existant():
            dernier = (MembreEglise.objects.filter(numero__startswith=prefixe).order_by("-numero")
                       .values_list("numero", flat=True).first())
            return int(dernier.rsplit("-", 1)[1]) if dernier else 0

        rang = Verrou.prendre(f"numero-membre:{prefixe}", initiale=plus_grand_existant)
        return f"{prefixe}{rang:05d}"

    def synchroniser_compte(self):
        """
        Le compte suit la fiche : un membre transféré ou décédé perd son accès,
        et un changement d'église locale déplace son compte dans le bon district.
        """
        if not self.compte_id:
            return
        u = self.compte
        if not self.actif and u.is_active:
            from core.jetons import revoquer_tout
            u.is_active = False
            u.save(update_fields=["is_active"])
            revoquer_tout(u)
        profil = getattr(u, "profil", None)
        if profil is not None and profil.district_id != self.paroisse.district_id:
            profil.district_id = self.paroisse.district_id
            profil.save(update_fields=["district"])


class DemandeAcces(models.Model):
    """
    Un fidèle demande lui-même l'accès à l'espace membre (depuis la page de connexion).
    Rien n'est ouvert sans la décision d'un administrateur.
    """

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        ACCORDEE = "ACCORDEE", "Accès accordé"
        REFUSEE = "REFUSEE", "Refusée"

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="demandes_acces")
    membre = models.ForeignKey(MembreEglise, null=True, blank=True, on_delete=models.SET_NULL, related_name="demandes_acces",
                               help_text="Fiche du registre reconnue (ou choisie par l'administrateur)")
    numero_saisi = models.CharField(max_length=24, blank=True)
    nom_saisi = models.CharField(max_length=160)
    telephone = models.CharField(max_length=30)
    message = models.CharField(max_length=500, blank=True)
    # Vrai quand le numéro de membre et le téléphone saisis correspondent à la fiche
    verifiee = models.BooleanField(default=False)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE)
    motif_refus = models.CharField(max_length=255, blank=True)
    traitee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    traitee_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["statut", "-cree_le"]
        verbose_name = "demande d'accès"
        verbose_name_plural = "demandes d'accès"
        indexes = [models.Index(fields=["organisation", "statut"])]

    def __str__(self):
        return f"Demande d'accès de {self.nom_saisi}"


# ====================================================================== 8. Dîmes et offrandes
class Contribution(models.Model):
    """
    Dîme, offrande ou cotisation d'un membre (ou collecte anonyme d'un culte).
    Chaque contribution reçoit un numéro de reçu unique et définitif. Elle ne se supprime pas :
    une erreur s'annule, avec son motif, et l'annulation est inscrite au journal d'audit.
    """

    class Type(models.TextChoices):
        DIME = "DIME", "Dîme"
        OFFRANDE = "OFFRANDE", "Offrande"
        ACTION_GRACES = "ACTION_GRACES", "Action de grâces"
        CONSTRUCTION = "CONSTRUCTION", "Construction"
        MISSION = "MISSION", "Mission et solidarité"
        MINISTERE = "MINISTERE", "Cotisation de ministère"
        AUTRE = "AUTRE", "Autre"

    class Mode(models.TextChoices):
        ESPECES = "ESPECES", "Espèces"
        MOBILE = "MOBILE", "Mobile Money"
        BANQUE = "BANQUE", "Banque"
        NATURE = "NATURE", "En nature (valorisé)"

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="contributions")
    paroisse = models.ForeignKey(Paroisse, on_delete=models.PROTECT, related_name="contributions")
    membre = models.ForeignKey(MembreEglise, null=True, blank=True, on_delete=models.PROTECT, related_name="contributions",
                               help_text="Vide = collecte anonyme (quête du culte)")
    type = models.CharField(max_length=14, choices=Type.choices, default=Type.DIME)
    montant = models.DecimalField(max_digits=14, decimal_places=0)
    date = models.DateField(default=date.today)
    mode = models.CharField(max_length=8, choices=Mode.choices, default=Mode.ESPECES)
    reference = models.CharField(max_length=60, blank=True, help_text="Référence Lumicash, EcoCash ou bancaire")
    note = models.CharField(max_length=255, blank=True)
    numero_recu = models.CharField(max_length=32, unique=True, editable=False)
    transaction = models.OneToOneField(Transaction, null=True, blank=True, on_delete=models.SET_NULL, related_name="contribution")
    enregistre_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    cree_le = models.DateTimeField(auto_now_add=True)
    annulee = models.BooleanField(default=False)
    annulee_le = models.DateTimeField(null=True, blank=True)
    annulee_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    motif_annulation = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "contribution"
        indexes = [models.Index(fields=["organisation", "date"]), models.Index(fields=["membre", "date"]),
                   models.Index(fields=["paroisse", "date"])]

    def __str__(self):
        return f"Reçu {self.numero_recu} — {self.get_type_display()} {self.montant}"

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.numero_recu:
                annee = self.date.year
                rang = Verrou.prendre(f"recu:{self.organisation_id}:{annee}")
                sigle = "".join(c for c in (self.organisation.sigle or "R").upper() if c.isalnum())[:12] or "R"
                self.numero_recu = f"{sigle}-{annee}-{rang:06d}"
            super().save(*args, **kwargs)


class AttestationAnnuelle(models.Model):
    """
    Attestation annuelle des contributions d'un membre. Chaque émission est conservée avec un code
    de vérification : n'importe qui (un employeur, une administration) peut vérifier son authenticité
    en scannant le QR code, sans voir le détail des dons.
    """

    membre = models.ForeignKey(MembreEglise, on_delete=models.CASCADE, related_name="attestations")
    annee = models.PositiveSmallIntegerField()
    total = models.DecimalField(max_digits=16, decimal_places=0)
    nombre = models.PositiveIntegerField()
    detail = models.JSONField(default=dict, help_text="Totaux par type au moment de l'émission")
    code = models.CharField(max_length=20, unique=True)
    definitive = models.BooleanField(default=True, help_text="Faux si l'année n'est pas terminée (attestation provisoire)")
    emise_le = models.DateTimeField(auto_now_add=True)
    emise_par = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-emise_le"]
        verbose_name = "attestation annuelle"

    def __str__(self):
        return f"Attestation {self.annee} de {self.membre} ({self.code})"
