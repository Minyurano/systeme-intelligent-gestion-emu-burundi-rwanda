"""Tests de la prévision financière : les mois incomplets ne doivent pas fausser la tendance."""
from datetime import date
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from core.models import District, Organisation
from finances.models import Transaction
from ia.predictions import prevision_financiere


class PrevisionFinanciereTests(TestCase):
    def setUp(self):
        org = Organisation.objects.create(nom="Église test", sigle="ET", slug="eglise-test-prev", pays="Burundi")
        self.district = District.objects.create(organisation=org, code="PRV", nom="Test", siege="Test")

    def _mois(self, annee, mois, recettes, depenses):
        Transaction.objects.create(date=date(annee, mois, 10), sens="RECETTE", categorie="DIME",
                                   montant=Decimal(recettes), district=self.district)
        Transaction.objects.create(date=date(annee, mois, 20), sens="DEPENSE", categorie="SALAIRE",
                                   montant=Decimal(depenses), district=self.district)

    def test_mois_de_fin_presque_vide_ecarte(self):
        for m in range(1, 10):                       # janvier à septembre : mois complets
            self._mois(2026, m, 100_000_000, 80_000_000)
        Transaction.objects.create(date=date(2026, 10, 2), sens="RECETTE", categorie="DIME",
                                   montant=Decimal(500_000), district=self.district)  # octobre : saisie à peine commencée
        with mock.patch("ia.predictions.timezone.localdate", return_value=date(2026, 11, 20)):
            r = prevision_financiere(Transaction.objects.all())
        self.assertEqual(r["mois_incomplets"], ["2026-10"])
        self.assertEqual(r["historique"][-1]["mois"], "2026-09")
        self.assertEqual([p["mois"] for p in r["prevision"]][:2], ["2026-10", "2026-11"])
        self.assertGreater(r["prevision"][0]["recettes"], 50_000_000)   # la tendance n'est pas tirée vers zéro

    def test_mois_en_cours_ecarte_meme_s_il_est_rempli(self):
        for m in range(1, 12):
            self._mois(2026, m, 100_000_000, 80_000_000)
        with mock.patch("ia.predictions.timezone.localdate", return_value=date(2026, 11, 20)):
            r = prevision_financiere(Transaction.objects.all())
        self.assertEqual(r["mois_incomplets"], ["2026-11"])
        self.assertEqual(len(r["prevision"]), 6)

    def test_historique_complet_inchange(self):
        for m in range(1, 10):
            self._mois(2026, m, 100_000_000, 80_000_000)
        with mock.patch("ia.predictions.timezone.localdate", return_value=date(2026, 11, 20)):
            r = prevision_financiere(Transaction.objects.all())
        self.assertEqual(r["mois_incomplets"], [])
        self.assertEqual(len(r["historique"]), 9)
