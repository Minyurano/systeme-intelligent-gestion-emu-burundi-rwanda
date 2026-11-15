import re

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils.text import slugify
from rest_framework import serializers

from .models import District, JournalAction, Organisation, Paroisse, Profil


class OrganisationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organisation
        fields = ["id", "nom", "sigle", "slug", "pays", "devise", "taux_usd", "langue", "statut", "portail_public", "whatsapp_numero",
                  "demandes_acces_ouvertes", "age_minimum_acces"]
        read_only_fields = ["slug", "statut"]

    def validate_age_minimum_acces(self, v):
        if not 10 <= v <= 21:
            raise serializers.ValidationError("Choisissez un âge entre 10 et 21 ans.")
        return v


class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        exclude = ["organisation"]


class ParoisseSerializer(serializers.ModelSerializer):
    district_nom = serializers.CharField(source="district.nom", read_only=True)

    class Meta:
        model = Paroisse
        fields = "__all__"


class JournalSerializer(serializers.ModelSerializer):
    utilisateur = serializers.CharField(source="utilisateur.username", default=None, read_only=True)

    class Meta:
        model = JournalAction
        exclude = ["organisation"]


class MembreSerializer(serializers.ModelSerializer):
    """Compte d'un membre de l'organisation, géré par son administrateur."""

    username = serializers.CharField(source="user.username")
    prenom = serializers.CharField(source="user.first_name", allow_blank=True, required=False)
    nom = serializers.CharField(source="user.last_name", allow_blank=True, required=False)
    email = serializers.EmailField(source="user.email", allow_blank=True, required=False)
    actif = serializers.BooleanField(source="user.is_active", required=False)
    derniere_connexion = serializers.DateTimeField(source="user.last_login", read_only=True)
    mot_de_passe = serializers.CharField(write_only=True, required=False, min_length=8)
    role_libelle = serializers.CharField(source="get_role_display", read_only=True)
    district_nom = serializers.CharField(source="district.nom", default=None, read_only=True)

    class Meta:
        model = Profil
        fields = ["id", "username", "prenom", "nom", "email", "actif", "derniere_connexion", "mot_de_passe",
                  "role", "role_libelle", "district", "district_nom", "telephone"]

    def validate_username(self, v):
        qs = User.objects.filter(username=v)
        if self.instance:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise serializers.ValidationError("Cet identifiant est déjà utilisé.")
        return v

    def validate_telephone(self, v):
        return re.sub(r"[^\d+]", "", v or "")

    def validate_role(self, v):
        if v == Profil.Role.MEMBRE:
            raise serializers.ValidationError("L'accès d'un membre de l'Église se donne depuis sa fiche du registre (page « Accès des membres »).")
        return v

    def validate(self, data):
        role = data.get("role", getattr(self.instance, "role", None))
        district = data.get("district", getattr(self.instance, "district", None))
        if role in (Profil.Role.SURINTENDANT, Profil.Role.AGENT) and not district:
            raise serializers.ValidationError({"district": "Un surintendant ou un agent doit être rattaché à un district."})
        if not self.instance and not data.get("mot_de_passe"):
            raise serializers.ValidationError({"mot_de_passe": "Choisissez un mot de passe d'au moins 8 caractères."})
        return data

    def create(self, data):
        u = data.pop("user")
        mdp = data.pop("mot_de_passe")
        user = User.objects.create_user(u["username"], email=u.get("email", ""), password=mdp,
                                        first_name=u.get("first_name", ""), last_name=u.get("last_name", ""))
        return Profil.objects.create(user=user, **data)

    def update(self, profil, data):
        u = data.pop("user", {})
        for k, v in u.items():
            setattr(profil.user, k, v)
        if data.get("mot_de_passe"):
            profil.user.set_password(data.pop("mot_de_passe"))
        profil.user.save()
        for k, v in data.items():
            setattr(profil, k, v)
        profil.save()
        return profil


class InscriptionSerializer(serializers.Serializer):
    """Création en libre-service d'une nouvelle organisation et de son administrateur."""

    nom = serializers.CharField(max_length=160)
    sigle = serializers.CharField(max_length=20)
    pays = serializers.CharField(max_length=80)
    devise = serializers.RegexField(r"^[A-Za-z]{3}$", error_messages={"invalid": "Code de monnaie à 3 lettres, par exemple RWF."})
    taux_usd = serializers.FloatField(min_value=0.0001)
    langue = serializers.ChoiceField(choices=["fr", "en"])
    districts = serializers.ListField(child=serializers.CharField(max_length=80), min_length=1, max_length=60)
    admin_prenom = serializers.CharField(max_length=60)
    admin_nom = serializers.CharField(max_length=60)
    admin_email = serializers.EmailField()
    admin_identifiant = serializers.CharField(max_length=60)
    admin_mot_de_passe = serializers.CharField(min_length=8, write_only=True)

    def validate_admin_identifiant(self, v):
        if User.objects.filter(username=v).exists():
            raise serializers.ValidationError("Cet identifiant est déjà utilisé.")
        return v

    def validate_admin_mot_de_passe(self, v):
        validate_password(v)
        return v

    def create(self, d):
        base = slugify(d["sigle"]) or slugify(d["nom"])[:40] or "organisation"
        slug, n = base, 2
        while Organisation.objects.filter(slug=slug).exists():
            slug, n = f"{base}-{n}", n + 1
        org = Organisation.objects.create(
            nom=d["nom"], sigle=d["sigle"], slug=slug, pays=d["pays"], devise=d["devise"].upper(),
            taux_usd=d["taux_usd"], langue=d["langue"], statut=Organisation.Statut.ESSAI,
        )
        codes = set()
        for nom in d["districts"]:
            nom = nom.strip()
            if not nom:
                continue
            code = re.sub(r"[^A-Z]", "", slugify(nom).upper())[:3] or "D"
            base_code, i = code, 2
            while code in codes:
                code, i = f"{base_code[:2]}{i}", i + 1
            codes.add(code)
            District.objects.create(organisation=org, code=code, nom=nom, siege=nom)
        user = User.objects.create_user(d["admin_identifiant"], email=d["admin_email"], password=d["admin_mot_de_passe"],
                                        first_name=d["admin_prenom"], last_name=d["admin_nom"])
        Profil.objects.create(user=user, organisation=org, role=Profil.Role.ADMIN)
        return org
