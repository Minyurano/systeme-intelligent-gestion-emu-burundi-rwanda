from rest_framework import serializers

from .models import (
    Avis, Bail, Budget, Campagne, ClotureExercice, Constat, Demande, Echeance, Fournisseur, Loyer, MembreEglise, OrdreTravail,
    PlanMaintenance,
)


def _nom(user):
    return (user.get_full_name() or user.username) if user else None


class AvisSerializer(serializers.ModelSerializer):
    utilisateur_nom = serializers.SerializerMethodField()
    role_libelle = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = Avis
        fields = ["id", "utilisateur_nom", "role", "role_libelle", "niveau", "decision", "commentaire", "date"]

    def get_utilisateur_nom(self, o):
        return _nom(o.utilisateur)


class DemandeSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    district_nom = serializers.CharField(source="district.nom", read_only=True)
    district_destination_nom = serializers.CharField(source="district_destination.nom", default=None, read_only=True)
    bien_nom = serializers.CharField(source="bien.nom", default=None, read_only=True)
    bien_code = serializers.CharField(source="bien.code", default=None, read_only=True)
    demandeur_nom = serializers.SerializerMethodField()
    role_attendu = serializers.CharField(read_only=True)
    avis = AvisSerializer(many=True, read_only=True)
    je_peux_valider = serializers.SerializerMethodField()
    je_peux_executer = serializers.SerializerMethodField()

    class Meta:
        model = Demande
        fields = "__all__"
        read_only_fields = ["organisation", "demandeur", "circuit", "niveau", "statut", "decide_le", "execute_le", "resultat"]

    def get_demandeur_nom(self, o):
        return _nom(o.demandeur)

    def _profil(self):
        from core.securite import profil_de
        return profil_de(self.context["request"].user)

    def get_je_peux_valider(self, o):
        from .services import peut_valider
        return peut_valider(self._profil(), o)

    def get_je_peux_executer(self, o):
        from .services import peut_executer
        return peut_executer(self._profil(), o)


class EcheanceSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    bien_nom = serializers.CharField(source="bien.nom", default=None, read_only=True)
    bien_code = serializers.CharField(source="bien.code", default=None, read_only=True)
    district_nom = serializers.CharField(source="district.nom", default=None, read_only=True)
    responsable_nom = serializers.SerializerMethodField()
    jours_restants = serializers.SerializerMethodField()

    class Meta:
        model = Echeance
        fields = "__all__"
        read_only_fields = ["organisation", "statut", "fait_le", "rappel_j30", "rappel_j7", "rappel_retard", "origine"]

    def get_responsable_nom(self, o):
        return _nom(o.responsable)

    def get_jours_restants(self, o):
        from datetime import date
        return (o.date - date.today()).days


class LoyerSerializer(serializers.ModelSerializer):
    statut = serializers.CharField(read_only=True)
    reste = serializers.DecimalField(max_digits=14, decimal_places=0, read_only=True)
    locataire = serializers.CharField(source="bail.locataire", read_only=True)
    bien_nom = serializers.CharField(source="bail.bien.nom", read_only=True)

    class Meta:
        model = Loyer
        fields = "__all__"
        read_only_fields = ["bail", "periode", "echeance", "montant_paye", "paye_le", "transaction"]


class BailSerializer(serializers.ModelSerializer):
    bien_nom = serializers.CharField(source="bien.nom", read_only=True)
    bien_code = serializers.CharField(source="bien.code", read_only=True)
    district_nom = serializers.CharField(source="bien.district.nom", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    impayes = serializers.SerializerMethodField()
    encaisse_annee = serializers.SerializerMethodField()

    class Meta:
        model = Bail
        fields = "__all__"
        read_only_fields = ["statut"]

    def get_impayes(self, o):
        from datetime import date
        return float(sum(l.reste for l in o.loyers.all() if l.echeance < date.today()))

    def get_encaisse_annee(self, o):
        from datetime import date
        return float(sum(l.montant_paye for l in o.loyers.all() if l.periode.year == date.today().year))


class FournisseurSerializer(serializers.ModelSerializer):
    nb_ordres = serializers.IntegerField(source="ordres.count", read_only=True)

    class Meta:
        model = Fournisseur
        fields = "__all__"
        read_only_fields = ["organisation"]


class PlanMaintenanceSerializer(serializers.ModelSerializer):
    bien_nom = serializers.CharField(source="bien.nom", read_only=True)
    bien_code = serializers.CharField(source="bien.code", read_only=True)
    fournisseur_nom = serializers.CharField(source="fournisseur.nom", default=None, read_only=True)

    class Meta:
        model = PlanMaintenance
        fields = "__all__"


class OrdreTravailSerializer(serializers.ModelSerializer):
    bien_nom = serializers.CharField(source="bien.nom", read_only=True)
    bien_code = serializers.CharField(source="bien.code", read_only=True)
    district_nom = serializers.CharField(source="bien.district.nom", read_only=True)
    fournisseur_nom = serializers.CharField(source="fournisseur.nom", default=None, read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    priorite_libelle = serializers.CharField(source="get_priorite_display", read_only=True)
    origine_libelle = serializers.CharField(source="get_origine_display", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)

    class Meta:
        model = OrdreTravail
        fields = "__all__"
        read_only_fields = ["origine", "plan", "demande", "transaction", "cree_par", "termine_le"]


class BudgetSerializer(serializers.ModelSerializer):
    categorie_libelle = serializers.CharField(source="get_categorie_display", read_only=True)
    district_nom = serializers.CharField(source="district.nom", default=None, read_only=True)

    class Meta:
        model = Budget
        fields = "__all__"
        read_only_fields = ["organisation"]


class ClotureSerializer(serializers.ModelSerializer):
    cloture_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = ClotureExercice
        fields = "__all__"
        read_only_fields = ["organisation", "cloture_par", "totaux"]

    def get_cloture_par_nom(self, o):
        return _nom(o.cloture_par)


class ConstatSerializer(serializers.ModelSerializer):
    bien_nom = serializers.CharField(source="bien.nom", read_only=True)
    bien_code = serializers.CharField(source="bien.code", read_only=True)
    etat_fiche = serializers.CharField(source="bien.etat", read_only=True)
    agent_nom = serializers.SerializerMethodField()

    class Meta:
        model = Constat
        fields = "__all__"

    def get_agent_nom(self, o):
        return _nom(o.agent)


class CampagneSerializer(serializers.ModelSerializer):
    district_nom = serializers.CharField(source="district.nom", default=None, read_only=True)
    nb_constats = serializers.IntegerField(source="constats.count", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)

    class Meta:
        model = Campagne
        fields = "__all__"
        read_only_fields = ["organisation", "statut", "cree_par", "cloturee_le", "proces_verbal"]


class MembreEgliseSerializer(serializers.ModelSerializer):
    paroisse_nom = serializers.CharField(source="paroisse.nom", read_only=True)
    district_nom = serializers.CharField(source="paroisse.district.nom", read_only=True)
    pasteur = serializers.CharField(source="paroisse.pasteur", read_only=True)
    sexe_libelle = serializers.CharField(source="get_sexe_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    situation_libelle = serializers.CharField(source="get_situation_familiale_display", read_only=True)
    enregistre_par_nom = serializers.SerializerMethodField()
    actif = serializers.BooleanField(read_only=True)

    class Meta:
        model = MembreEglise
        fields = "__all__"
        # Le compte se donne uniquement par « Accès des membres » (jamais par une modification de fiche)
        read_only_fields = ["numero", "enregistre_par", "cree_le", "modifie_le", "compte"]

    def get_enregistre_par_nom(self, o):
        return _nom(o.enregistre_par)

    def validate(self, data):
        nom = (data.get("nom") or getattr(self.instance, "nom", "")).strip()
        prenom = (data.get("prenom") or getattr(self.instance, "prenom", "")).strip()
        if len(nom) < 2 or len(prenom) < 2:
            raise serializers.ValidationError("Le nom et le prénom sont obligatoires.")
        data["nom"], data["prenom"] = nom.upper(), prenom[:1].upper() + prenom[1:]
        naissance = data.get("date_naissance", getattr(self.instance, "date_naissance", None))
        from datetime import date
        if naissance and naissance > date.today():
            raise serializers.ValidationError({"date_naissance": "La date de naissance est dans le futur."})
        bapteme = data.get("date_bapteme", getattr(self.instance, "date_bapteme", None))
        if naissance and bapteme and bapteme < naissance:
            raise serializers.ValidationError({"date_bapteme": "Le baptême ne peut pas précéder la naissance."})
        # Doublon : même nom, même prénom et même date de naissance dans l'organisation
        paroisse = data.get("paroisse") or getattr(self.instance, "paroisse", None)
        if paroisse is not None and not self.initial_data.get("confirmer_doublon"):
            qs = MembreEglise.objects.filter(nom__iexact=data["nom"], prenom__iexact=data["prenom"],
                                             paroisse__district__organisation_id=paroisse.district.organisation_id)
            if naissance:
                qs = qs.filter(date_naissance=naissance)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            existant = qs.select_related("paroisse").first()
            if existant:
                raise serializers.ValidationError({"doublon": f"Une fiche existe déjà : {existant.numero}, {existant.prenom} {existant.nom} "
                                                              f"({existant.paroisse.nom}). Cochez « confirmer » si c'est une autre personne."})
        return data
