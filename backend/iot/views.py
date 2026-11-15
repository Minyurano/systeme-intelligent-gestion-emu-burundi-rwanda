from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from core.models import Profil
from core.securite import DistrictScopedMixin, JournalMixin

from .models import Alerte, Capteur, Mesure
from .serializers import AlerteSerializer, CapteurSerializer, MesureSerializer
from .services import enregistrer_mesure

R = Profil.Role


class CapteurViewSet(DistrictScopedMixin, JournalMixin, viewsets.ModelViewSet):
    queryset = Capteur.objects.select_related("bien", "bien__district")
    serializer_class = CapteurSerializer
    district_field = "bien__district"
    roles_ecriture = (R.ADMIN,)
    filterset_fields = ["type", "bien", "actif"]
    pagination_class = None

    @action(detail=True)
    def mesures(self, request, pk=None):
        """Historique des mesures (par défaut 7 jours)."""
        capteur = self.get_object()
        jours = int(request.query_params.get("jours", 7))
        qs = capteur.mesures.filter(horodatage__gte=timezone.now() - timedelta(days=jours)).order_by("horodatage")
        return Response(MesureSerializer(qs, many=True).data)


class AlerteViewSet(DistrictScopedMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Alerte.objects.select_related("bien", "bien__district")
    serializer_class = AlerteSerializer
    district_field = "bien__district"
    filterset_fields = ["resolue", "niveau", "bien"]
    pagination_class = None

    @action(detail=True, methods=["post"])
    def resoudre(self, request, pk=None):
        alerte = self.get_object()
        alerte.resolue = True
        alerte.save(update_fields=["resolue"])
        return Response(self.get_serializer(alerte).data)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def ingestion(request):
    """
    Point d'entrée des capteurs (ESP32, passerelle LoRaWAN, broker MQTT...).
    En-tête : X-API-Key: <IOT_API_KEY>
    Corps   : {"capteur": "FOR-MUY-01", "valeur": 3.4, "horodatage": "2026-10-08T10:00:00Z"}
              ou une liste de tels objets (envoi groupé après une coupure réseau).
    """
    if request.headers.get("X-API-Key") != settings.UMURAGE["IOT_API_KEY"]:
        return Response({"erreur": "Clé API invalide"}, status=status.HTTP_401_UNAUTHORIZED)
    lots = request.data if isinstance(request.data, list) else [request.data]
    enregistres, erreurs = 0, []
    for m in lots:
        try:
            capteur = Capteur.objects.get(code=m["capteur"], actif=True)
            h = parse_datetime(m["horodatage"]) if m.get("horodatage") else None
            enregistrer_mesure(capteur, float(m["valeur"]), h)
            enregistres += 1
        except Capteur.DoesNotExist:
            erreurs.append(f"Capteur inconnu ou inactif : {m.get('capteur')}")
        except (KeyError, ValueError, TypeError) as e:
            erreurs.append(f"Mesure invalide : {e}")
    return Response({"enregistrees": enregistres, "erreurs": erreurs},
                    status=status.HTTP_201_CREATED if enregistres else status.HTTP_400_BAD_REQUEST)
