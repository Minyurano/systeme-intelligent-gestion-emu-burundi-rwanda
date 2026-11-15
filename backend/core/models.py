import hashlib
import json

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models import F


class Organisation(models.Model):
    """
    Une Église, une conférence ou une organisation qui utilise UMURAGE.
    Une seule installation sert plusieurs organisations : leurs données sont
    strictement séparées.
    """

    class Statut(models.TextChoices):
        ESSAI = "ESSAI", "Période d'essai"
        ACTIF = "ACTIF", "Active"
        SUSPENDU = "SUSPENDU", "Suspendue"

    nom = models.CharField(max_length=160)
    sigle = models.CharField(max_length=20)
    slug = models.SlugField(max_length=60, unique=True, help_text="Identifiant dans les adresses, ex. emu-burundi")
    pays = models.CharField(max_length=80)
    devise = models.CharField(max_length=3, default="BIF", help_text="Code ISO 4217 de la monnaie locale (BIF, RWF, KES...)")
    taux_usd = models.FloatField(default=2950, help_text="Unités de monnaie locale pour 1 USD")
    langue = models.CharField(max_length=5, default="fr", choices=[("fr", "Français"), ("en", "English")])
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    portail_public = models.BooleanField(default=True, help_text="Publier le portail de transparence")
    whatsapp_numero = models.CharField(max_length=30, blank=True, help_text="Numéro WhatsApp Business qui reçoit les déclarations")
    age_minimum_acces = models.PositiveSmallIntegerField(
        default=16, help_text="Âge à partir duquel un membre reçoit un accès sans accord d'un parent ou tuteur"
    )
    demandes_acces_ouvertes = models.BooleanField(
        default=True, help_text="Les membres inscrits au registre peuvent demander eux-mêmes un accès à l'espace membre"
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class District(models.Model):
    """District (ou diocèse, région...) d'une organisation."""

    organisation = models.ForeignKey(Organisation, null=True, on_delete=models.CASCADE, related_name="districts")
    code = models.CharField(max_length=5)  # ex. GIT
    nom = models.CharField(max_length=80)
    siege = models.CharField(max_length=80)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    surintendant = models.CharField(max_length=120, blank=True)
    # Anciens districts (découpage à 11) rattachés à celui-ci, séparés par des virgules
    anciens_districts = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["nom"]
        unique_together = ("organisation", "code")

    def __str__(self):
        return self.nom


class Paroisse(models.Model):
    nom = models.CharField(max_length=120)
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="paroisses")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    pasteur = models.CharField(max_length=120, blank=True)
    membres = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["nom"]
        unique_together = ("nom", "district")

    def __str__(self):
        return f"{self.nom} ({self.district.nom})"


class Profil(models.Model):
    """Rôle d'un utilisateur. Le rôle détermine ce qu'il voit et modifie."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrateur"
        EVEQUE = "EVEQUE", "Évêque / Direction"
        TRESORIER = "TRESORIER", "Trésorier"
        SURINTENDANT = "SURINTENDANT", "Surintendant de district"
        AGENT = "AGENT", "Agent de collecte"
        # Simple fidèle : accès donné par un administrateur, limité à son espace membre
        MEMBRE = "MEMBRE", "Membre de l'Église"

    user =models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profil")
    organisation = models.ForeignKey(Organisation, null=True, on_delete=models.CASCADE, related_name="membres")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.AGENT)
    district = models.ForeignKey(District, null=True, blank=True, on_delete=models.SET_NULL)
    telephone = models.CharField(max_length=30, blank=True)
    # Double authentification (application Google Authenticator, Microsoft Authenticator...)
    totp_secret = models.CharField(max_length=64, blank=True)
    totp_actif = models.BooleanField(default=False)
    # Mot de passe provisoire (accès donné par un administrateur) : à changer à la première connexion
    doit_changer_mdp = models.BooleanField(default=False)

    @property
    def voit_tout(self):
        return self.role in (self.Role.ADMIN, self.Role.EVEQUE, self.Role.TRESORIER)

    @property
    def est_membre_simple(self):
        """Un fidèle n'accède qu'à son espace membre, jamais aux outils de gestion."""
        return self.role == self.Role.MEMBRE

    def __str__(self):
        return f"{self.user.username} — {self.get_role_display()}"


class Verrou(models.Model):
    """
    Verrou et compteur partagés entre les requêtes simultanées.

    `prendre()` modifie la ligne : PostgreSQL la verrouille jusqu'à la fin de la transaction,
    SQLite verrouille toute la base en écriture. Deux enregistrements simultanés passent donc
    l'un après l'autre, au lieu de lire la même « dernière valeur ».
    """

    nom = models.CharField(max_length=80, unique=True)
    valeur = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = "verrou"

    def __str__(self):
        return f"{self.nom} = {self.valeur}"

    @classmethod
    def prendre(cls, nom, initiale=None):
        """
        À appeler dans une transaction. Verrouille `nom` et renvoie le compteur incrémenté.
        `initiale` : fonction qui donne la valeur de départ si le compteur n'existe pas encore
        (par exemple le plus grand numéro déjà attribué avant l'introduction du compteur).
        """
        if not transaction.get_connection().in_atomic_block:
            raise RuntimeError("Verrou.prendre() doit être appelé dans transaction.atomic().")
        if not cls.objects.filter(nom=nom).update(valeur=F("valeur") + 1):
            try:
                with transaction.atomic():
                    cls.objects.create(nom=nom, valeur=initiale() if initiale else 0)
            except IntegrityError:
                pass  # créé au même instant par une autre requête : on attend simplement son verrou
            cls.objects.filter(nom=nom).update(valeur=F("valeur") + 1)
        return cls.objects.values_list("valeur", flat=True).get(nom=nom)


class CodeReinitialisation(models.Model):
    """
    Code à 6 chiffres pour choisir un nouveau mot de passe (« mot de passe oublié »).
    Seule son empreinte est conservée ; il expire après 10 minutes et 5 essais.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="codes_reinitialisation")
    empreinte = models.CharField(max_length=64)
    cree_le = models.DateTimeField(auto_now_add=True)
    expire_le = models.DateTimeField()
    essais = models.PositiveSmallIntegerField(default=0)
    utilise = models.BooleanField(default=False)
    canaux = models.CharField(max_length=40, blank=True, help_text="WhatsApp, e-mail…")

    class Meta:
        ordering = ["-cree_le"]
        verbose_name = "code de réinitialisation"


class JournalAction(models.Model):
    """
    Journal d'audit : qui a modifié quoi, et quand.

    Chaque entrée contient l'empreinte SHA-256 de l'entrée précédente, comme les blocs
    d'une blockchain : modifier ou supprimer une ancienne entrée casse la chaîne, ce que
    `verifier_chaine()` détecte. C'est la première brique du registre infalsifiable.
    """

    date = models.DateTimeField()
    organisation = models.ForeignKey(Organisation, null=True, blank=True, on_delete=models.CASCADE)
    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=20)  # CREATION / MODIFICATION / SUPPRESSION
    objet_type = models.CharField(max_length=60)
    objet_id = models.CharField(max_length=40)
    objet_libelle = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)
    empreinte_precedente = models.CharField(max_length=64, blank=True, editable=False)
    empreinte = models.CharField(max_length=64, blank=True, editable=False)

    class Meta:
        ordering = ["-date", "-id"]

    def calculer_empreinte(self):
        contenu = json.dumps(
            [self.empreinte_precedente, self.date.isoformat(), self.utilisateur_id, self.action,
             self.objet_type, self.objet_id, self.objet_libelle, self.details],
            sort_keys=True, ensure_ascii=False, default=str,
        )
        return hashlib.sha256(contenu.encode()).hexdigest()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Une entrée du journal d'audit ne peut pas être modifiée.")
        from django.utils import timezone

        # Le verrou garantit qu'une seule écriture à la fois lit le dernier maillon de la chaîne :
        # sans lui, deux actions simultanées reprendraient la même empreinte précédente et la
        # vérification signalerait une fausse falsification.
        with transaction.atomic():
            Verrou.prendre("journal-audit")
            self.date = timezone.now()
            dernier = JournalAction.objects.order_by("-id").only("empreinte").first()
            self.empreinte_precedente = dernier.empreinte if dernier else "0" * 64
            self.empreinte = self.calculer_empreinte()
            super().save(*args, **kwargs)

    @classmethod
    def verifier_chaine(cls):
        """Renvoie (True, n) si la chaîne est intacte, sinon (False, id de la première entrée altérée)."""
        precedente = "0" * 64
        n = 0
        for e in cls.objects.order_by("id").iterator():
            if e.empreinte_precedente != precedente or e.calculer_empreinte() != e.empreinte:
                return False, e.id
            precedente = e.empreinte
            n += 1
        return True, n
