from rest_framework import serializers

from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    district_nom = serializers.CharField(source="district.nom", read_only=True)
    projet_nom = serializers.CharField(source="projet.nom", default=None, read_only=True)
    categorie_libelle = serializers.CharField(source="get_categorie_display", read_only=True)
    canal_libelle = serializers.CharField(source="get_canal_display", read_only=True)

    class Meta:
        model = Transaction
        fields = "__all__"
        read_only_fields = ["montant_bif", "score_anomalie", "est_anomalie", "motifs_anomalie"]

    def validate(self, attrs):
        """Aucune écriture sur un exercice clôturé, ni pour la nouvelle date ni pour l'ancienne."""
        from core.securite import profil_de
        from metier.services import verifier_exercice_ouvert

        profil = profil_de(self.context["request"].user)
        if profil:
            if self.instance is not None:
                verifier_exercice_ouvert(profil.organisation_id, self.instance.date)
            verifier_exercice_ouvert(profil.organisation_id, attrs.get("date") or getattr(self.instance, "date", None))
        return attrs
