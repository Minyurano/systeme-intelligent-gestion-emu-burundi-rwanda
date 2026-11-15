from rest_framework import serializers

from .models import Alerte, Capteur, Mesure


class CapteurSerializer(serializers.ModelSerializer):
    bien_nom = serializers.CharField(source="bien.nom", read_only=True)
    district_nom = serializers.CharField(source="bien.district.nom", read_only=True)
    type_libelle = serializers.CharField(source="get_type_display", read_only=True)
    en_alerte = serializers.SerializerMethodField()

    class Meta:
        model = Capteur
        fields = "__all__"
        read_only_fields = ["derniere_valeur", "derniere_mesure"]

    def get_en_alerte(self, obj):
        return obj.alertes.filter(resolue=False).exists()


class MesureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mesure
        fields = ["id", "capteur", "horodatage", "valeur"]


class AlerteSerializer(serializers.ModelSerializer):
    bien_nom = serializers.CharField(source="bien.nom", read_only=True)
    district_nom = serializers.CharField(source="bien.district.nom", read_only=True)
    niveau_libelle = serializers.CharField(source="get_niveau_display", read_only=True)

    class Meta:
        model = Alerte
        fields = "__all__"
