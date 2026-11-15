"""API des déclarations de terrain et webhook WhatsApp."""
import os

from django.utils import timezone
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.http import HttpResponse

from core.models import Profil
from core.securite import DistrictScopedMixin, JournalMixin, profil_de

from . import whatsapp
from .models import Bien, Declaration, Mouvement
from .serializers import BienSerializer

R = Profil.Role


class DeclarationSerializer(serializers.ModelSerializer):
    district_nom = serializers.CharField(source="district.nom", default=None, read_only=True)
    canal_libelle = serializers.CharField(source="get_canal_display", read_only=True)
    statut_libelle = serializers.CharField(source="get_statut_display", read_only=True)
    bien_code = serializers.CharField(source="bien.code", default=None, read_only=True)

    class Meta:
        model = Declaration
        exclude = ["organisation"]


class DeclarationViewSet(DistrictScopedMixin, JournalMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Declaration.objects.select_related("district", "bien")
    serializer_class = DeclarationSerializer
    filterset_fields = ["statut", "canal", "district"]
    # Tout le monde peut utiliser le simulateur ; seuls les responsables valident
    roles_ecriture = (R.ADMIN, R.SURINTENDANT, R.EVEQUE, R.AGENT, R.TRESORIER)
    roles_validation = (R.ADMIN, R.SURINTENDANT, R.EVEQUE)

    def _peut_valider(self):
        if profil_de(self.request.user).role not in self.roles_validation:
            raise PermissionDenied("La validation est réservée aux surintendants et à la direction.")

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        """Crée le bien à partir de la déclaration ; le validateur peut corriger chaque champ."""
        self._peut_valider()
        d = self.get_object()
        if d.statut != Declaration.Statut.EN_ATTENTE:
            raise ValidationError("Cette déclaration a déjà été traitée.")
        i = d.interpretation or {}
        existant = i.get("bien_existant")
        if request.data.get("mode") == "mise_a_jour" and existant:
            return self._mettre_a_jour(d, existant["id"], request)
        donnees = {
            "nom": i.get("nom") or "Bien déclaré", "categorie": i.get("categorie"), "sous_type": i.get("sous_type") or "",
            "etat": i.get("etat") or "BON", "district": d.district_id, "paroisse": i.get("paroisse"),
            "quantite": i.get("quantite") or 1, "valeur_acquisition": i.get("valeur_acquisition") or 0,
            "surface_m2": i.get("surface_m2"), "financeur": i.get("financeur") or "",
            "responsable": d.auteur_nom, "date_acquisition": timezone.localdate().isoformat(),
            "description": f"Déclaré par {d.auteur_nom} via {d.get_canal_display()} : « {d.texte or d.transcription} »",
        }
        modifiables = {n for n, f in BienSerializer().fields.items() if not f.read_only}
        donnees.update({k: v for k, v in request.data.items() if k in modifiables})  # corrections du validateur
        s = BienSerializer(data=donnees)
        s.is_valid(raise_exception=True)
        self._verifier_district(s)
        bien = s.save()
        if d.media and d.media_type == "image":
            bien.photo.save(os.path.basename(d.media.name), d.media.file, save=True)
        from ia import predictions, valorisation  # recalcul immédiat de la valeur et du risque
        try:
            res = valorisation.estimer(bien)
            bien.valeur_estimee, bien.methode_valorisation = int(res["valeur"]), res["methode"]
        except Exception:
            pass
        bien.score_risque, _ = predictions.score_risque(bien)
        bien.save()
        d.statut, d.bien, d.traitee_par, d.traitee_le = Declaration.Statut.VALIDEE, bien, request.user.get_full_name() or request.user.username, timezone.now()
        d.save()
        self._journaliser("CREATION", bien, {"source": {"avant": "", "apres": f"Déclaration {d.pk} ({d.get_canal_display()})"}})
        whatsapp.envoyer(d.expediteur, f"Votre déclaration n° {d.pk} est validée : {bien.nom} est enregistré sous le code {bien.code}. Merci !")
        return Response(self.get_serializer(d).data)

    def _mettre_a_jour(self, d, bien_id, request):
        """Le message signale un problème sur un bien existant : on met à jour son état et son historique."""
        from ia import predictions

        bien = Bien.objects.get(pk=bien_id, district__organisation_id=d.organisation_id)
        ancien = bien.get_etat_display()
        nouvel_etat = request.data.get("etat") or d.interpretation.get("etat") or bien.etat
        bien.etat = nouvel_etat
        bien.save()
        Mouvement.objects.create(bien=bien, type="INSPECTION", date=timezone.localdate(), auteur=d.auteur_nom,
                                 description=f"Signalé via {d.get_canal_display()} : « {d.texte or d.transcription} »")
        bien.score_risque, _ = predictions.score_risque(bien)
        bien.save(update_fields=["score_risque"])
        d.statut, d.bien, d.traitee_par, d.traitee_le = Declaration.Statut.VALIDEE, bien, request.user.get_full_name() or request.user.username, timezone.now()
        d.save()
        self._journaliser("MODIFICATION", bien, {"etat": {"avant": ancien, "apres": bien.get_etat_display()}})
        whatsapp.envoyer(d.expediteur, f"Merci ! Votre signalement n° {d.pk} a été enregistré sur {bien.code} — {bien.nom}.")
        return Response(self.get_serializer(d).data)

    @action(detail=True, methods=["post"])
    def rejeter(self, request, pk=None):
        self._peut_valider()
        d = self.get_object()
        if d.statut != Declaration.Statut.EN_ATTENTE:
            raise ValidationError("Cette déclaration a déjà été traitée.")
        d.statut = Declaration.Statut.REJETEE
        d.motif_rejet = (request.data.get("motif") or "")[:255]
        d.traitee_par, d.traitee_le = request.user.get_full_name() or request.user.username, timezone.now()
        d.save()
        whatsapp.envoyer(d.expediteur, f"Votre déclaration n° {d.pk} n'a pas été retenue. Motif : {d.motif_rejet or 'non précisé'}.")
        return Response(self.get_serializer(d).data)

    @action(detail=False, methods=["post"])
    def simuler(self, request):
        """Simulateur intégré : envoie un message « comme sur WhatsApp » depuis l'application."""
        profil = profil_de(request.user)
        tel = request.data.get("telephone") or profil.telephone
        if not tel:
            raise ValidationError({"telephone": "Indiquez un numéro enregistré dans un compte de votre organisation."})
        cible = whatsapp.trouver_profil(tel)
        if cible and cible.organisation_id != profil.organisation_id:
            raise PermissionDenied("Ce numéro appartient à une autre organisation.")
        media = None
        f = request.FILES.get("media")
        if f:
            media = {"contenu": f.read(), "type": "audio" if f.content_type.startswith("audio") else "image", "nom": f.name}
        d, reponse = whatsapp.traiter_message(tel, request.data.get("texte", ""), media)
        return Response({"reponse": reponse, "declaration": self.get_serializer(d).data if d else None})


@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def webhook_whatsapp(request):
    """Adresse à déclarer dans l'application Meta : https://votre-domaine/api/whatsapp/webhook/"""
    if request.method == "GET":
        attendu = os.environ.get("WHATSAPP_VERIFY_TOKEN")
        if attendu and request.query_params.get("hub.verify_token") == attendu and request.query_params.get("hub.mode") == "subscribe":
            return HttpResponse(request.query_params.get("hub.challenge", ""))
        return HttpResponse("Jeton de vérification invalide", status=403)

    for msg in whatsapp.messages_du_webhook(request.data):
        expediteur, genre = msg.get("from", ""), msg.get("type")
        texte, media = "", None
        if genre == "text":
            texte = msg.get("text", {}).get("body", "")
        elif genre in ("image", "audio"):
            contenu = msg.get(genre, {})
            texte = contenu.get("caption", "")
            brut = whatsapp.telecharger_media(contenu.get("id"))
            if brut:
                ext = ".jpg" if genre == "image" else ".ogg"
                media = {"contenu": brut["contenu"], "type": genre, "nom": f"whatsapp_{msg.get('id', 'media')}{ext}"}
        _, reponse = whatsapp.traiter_message(expediteur, texte, media)
        whatsapp.envoyer(expediteur, reponse)
    return Response({"statut": "reçu"}, status=status.HTTP_200_OK)
