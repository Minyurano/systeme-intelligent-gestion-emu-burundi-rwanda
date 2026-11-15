from rest_framework import serializers

from .models import ODD_LIBELLES, Bien, Document, Mouvement, Projet


class BienSerializer(serializers.ModelSerializer):
    district_nom = serializers.CharField(source="district.nom", read_only=True)
    paroisse_nom = serializers.CharField(source="paroisse.nom", default=None, read_only=True)
    categorie_libelle = serializers.CharField(source="get_categorie_display", read_only=True)
    etat_libelle = serializers.CharField(source="get_etat_display", read_only=True)
    juridique_libelle = serializers.CharField(source="get_statut_juridique_display", read_only=True)
    age_ans = serializers.FloatField(read_only=True)
    valeur_courante = serializers.DecimalField(max_digits=16, decimal_places=0, read_only=True)
    odd_libelles = serializers.SerializerMethodField()

    class Meta:
        model = Bien
        fields = "__all__"
        read_only_fields = ["code", "valeur_estimee", "methode_valorisation", "score_risque", "date_sortie"]

    def get_odd_libelles(self, obj):
        return [ODD_LIBELLES.get(o.strip(), f"ODD {o.strip()}") for o in obj.odd.split(",") if o.strip()]

    def validate(self, data):
        paroisse = data.get("paroisse") or getattr(self.instance, "paroisse", None)
        district = data.get("district") or getattr(self.instance, "district", None)
        if paroisse and district and paroisse.district_id != district.pk:
            raise serializers.ValidationError({"paroisse": "Cette paroisse n'appartient pas au district choisi."})
        return data


class MouvementSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    bien_nom = serializers.CharField(source="bien.nom", read_only=True)

    class Meta:
        model = Mouvement
        fields = "__all__"


class DocumentSerializer(serializers.ModelSerializer):
    organisation = serializers.PrimaryKeyRelatedField(read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    bien_nom = serializers.CharField(source="bien.nom", default=None, read_only=True)
    district_nom = serializers.CharField(source="district.nom", default=None, read_only=True)
    taille_texte = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = "__all__"
        extra_kwargs = {"contenu": {"required": False}}

    def get_taille_texte(self, obj):
        return len(obj.contenu or "")


class ProjetSerializer(serializers.ModelSerializer):
    district_nom = serializers.CharField(source="district.nom", read_only=True)
    domaine_libelle = serializers.CharField(source="get_domaine_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    taux_execution = serializers.SerializerMethodField()

    class Meta:
        model = Projet
        fields = "__all__"

    def get_taux_execution(self, obj):
        return round(100 * float(obj.depense) / float(obj.budget), 1) if obj.budget else None
