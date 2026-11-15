from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.models import Profil
from core.securite import profil_de

from . import anomalies, assistant, predictions, valorisation
from finances.models import Transaction
from patrimoine.models import Bien

from .models import EntrainementModele

R = Profil.Role


@api_view(["POST"])
def poser_question(request):
    question = (request.data.get("question") or "").strip()
    if len(question) < 3:
        return Response({"erreur": "Question trop courte."}, status=400)
    return Response(assistant.repondre(question, profil_de(request.user)))


@api_view(["POST"])
def relancer_analyses(request):
    """Ré-entraîne les modèles et recalcule valeurs, risques et anomalies."""
    profil = profil_de(request.user)
    if profil.role not in (R.ADMIN, R.TRESORIER, R.EVEQUE):
        raise PermissionDenied("Réservé à la direction et au trésorier.")
    org = profil.organisation_id
    try:
        metriques = valorisation.entrainer(org)
    except ValueError as e:
        metriques = {"r2_validation_croisee": None, "avertissement": str(e)}
    biens = Bien.objects.filter(district__organisation_id=org).select_related("district")
    return Response({
        "valorisation": {"biens_valorises": valorisation.valoriser_tout(biens), **metriques},
        "risques": {"biens_evalues": predictions.recalculer_risques(biens)},
        "anomalies": anomalies.analyser(Transaction.objects.filter(district__organisation_id=org)),
    })


@api_view(["GET"])
def historique_modeles(request):
    return Response(list(EntrainementModele.objects.values("modele", "date", "nb_exemples", "metriques")[:20]))
