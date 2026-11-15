"""Adresse IP réelle derrière un proxy : les limites de tentatives ne se contournent pas en falsifiant X-Forwarded-For."""
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import Organisation, Profil

URL = "/api/auth/mot-de-passe-oublie/"  # limité à 5 demandes par heure et par adresse
LIMITE = 5


def reglage(n):
    return override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, "NUM_PROXIES": n})


class AdresseReelleTests(TestCase):
    def setUp(self):
        cache.clear()

    def demander(self, xff=None, remote="10.0.0.1"):
        entetes = {"REMOTE_ADDR": remote}
        if xff:
            entetes["HTTP_X_FORWARDED_FOR"] = xff
        return APIClient().post(URL, {"identifiant": "personne"}, format="json", **entetes).status_code

    def test_reglage_par_defaut_ignore_l_entete_falsifie(self):
        self.assertEqual(settings.REST_FRAMEWORK["NUM_PROXIES"], 0)
        codes = [self.demander(xff=f"203.0.113.{i}") for i in range(LIMITE + 1)]
        self.assertEqual(codes[-1], 429, "changer X-Forwarded-For ne doit pas remettre le compteur à zéro")

    @reglage(1)
    def test_derriere_un_proxy_on_prend_l_adresse_ajoutee_par_le_proxy(self):
        # Le client invente la première adresse ; le proxy ajoute la vraie (198.51.100.7) à la fin
        codes = [self.demander(xff=f"1.2.3.{i}, 198.51.100.7", remote="172.18.0.1") for i in range(LIMITE + 1)]
        self.assertEqual(codes[:LIMITE], [200] * LIMITE)
        self.assertEqual(codes[-1], 429)
        # Un autre visiteur, derrière le même proxy, n'est pas bloqué
        self.assertEqual(self.demander(xff="198.51.100.8", remote="172.18.0.1"), 200)

    @reglage(0)
    def test_sans_proxy_tous_les_visiteurs_ne_sont_pas_confondus(self):
        for _ in range(LIMITE):
            self.demander(remote="192.0.2.10")
        self.assertEqual(self.demander(remote="192.0.2.10"), 429)
        self.assertEqual(self.demander(remote="192.0.2.11"), 200)

    @reglage(1)
    def test_diagnostic_reserve_a_l_administrateur(self):
        org = Organisation.objects.create(nom="Test", sigle="T", slug="t", pays="Burundi")
        for nom, role in (("adm", Profil.Role.ADMIN), ("tre", Profil.Role.TRESORIER)):
            u = User.objects.create_user(nom, password="Motdepasse-2026")
            Profil.objects.create(user=u, organisation=org, role=role)
        c = APIClient()
        c.force_authenticate(User.objects.get(username="adm"))
        r = c.get("/api/diagnostic/adresse-ip/", REMOTE_ADDR="172.18.0.1", HTTP_X_FORWARDED_FOR="9.9.9.9, 198.51.100.7")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["adresse_retenue"], "198.51.100.7")
        c.force_authenticate(User.objects.get(username="tre"))
        self.assertEqual(c.get("/api/diagnostic/adresse-ip/").status_code, 403)
