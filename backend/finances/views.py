from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import Profil
from core.securite import DistrictScopedMixin, JournalMixin
from ia.predictions import prevision_financiere

from .models import Transaction
from .serializers import TransactionSerializer

R = Profil.Role


class TransactionViewSet(DistrictScopedMixin, JournalMixin, viewsets.ModelViewSet):
    queryset = Transaction.objects.select_related("district", "projet")
    serializer_class = TransactionSerializer
    roles_ecriture = (R.ADMIN, R.TRESORIER)
    filterset_fields = {
        "district": ["exact"], "sens": ["exact"], "categorie": ["exact"], "canal": ["exact"],
        "est_anomalie": ["exact"], "verifiee": ["exact"], "rapprochee": ["exact"], "bien": ["exact"], "date": ["gte", "lte"],
    }
    search_fields = ["tiers", "description", "reference_externe"]
    ordering_fields = ["date", "montant_bif", "score_anomalie"]

    def perform_destroy(self, instance):
        from metier.services import verifier_exercice_ouvert

        verifier_exercice_ouvert(instance.district.organisation_id, instance.date)
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def verifier(self, request, pk=None):
        """Le trésorier confirme avoir contrôlé une transaction signalée."""
        t = self.get_object()
        t.verifiee = True
        t.save(update_fields=["verifiee"])
        self._journaliser("MODIFICATION", t, {"verifiee": {"avant": "False", "apres": "True"}})
        return Response(self.get_serializer(t).data)

    @action(detail=False)
    def synthese(self, request):
        qs = self.filter_queryset(self.get_queryset())
        par_cat = (
            qs.values("sens", "categorie").annotate(total=Sum("montant_bif")).order_by("sens", "-total")
        )
        libelles = dict(Transaction.Categorie.choices)
        return Response({
            "par_categorie": [
                {"sens": r["sens"], "categorie": libelles[r["categorie"]], "total": float(r["total"])} for r in par_cat
            ],
            "prevision": prevision_financiere(qs),
        })
