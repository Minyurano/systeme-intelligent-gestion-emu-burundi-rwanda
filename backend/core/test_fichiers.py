"""Tests 3.9 : fichiers téléversés protégés (liens signés et temporaires), réglages stricts de production."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import override_settings
from rest_framework.test import APIClient

from core.models import District
from core.tests import Base
from patrimoine.models import Document

MEDIA_TEST = tempfile.mkdtemp(prefix="umurage-media-")


@override_settings(MEDIA_ROOT=MEDIA_TEST)
class FichiersProtegesTests(Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        gitega = District.objects.filter(nom__icontains="gitega").select_related("organisation").first()
        cls.doc = Document(titre="Titre foncier test", organisation=gitega.organisation, district=gitega, type="TITRE_FONCIER")
        cls.doc.fichier.save("titre_test.pdf", ContentFile(b"%PDF-1.4 titre foncier"), save=True)
        piege = Document(titre="Fichier piégé", organisation=gitega.organisation, district=None)
        piege.fichier.save("piege.html", ContentFile(b"<script>alert(1)</script>"), save=True)
        cls.brut = "/media/" + cls.doc.fichier.name
        cls.piege = piege

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEST, ignore_errors=True)

    def lien(self, username, doc=None):
        doc = doc or self.doc
        r = self.client_pour(username).get(f"/api/documents/{doc.pk}/")
        self.assertEqual(r.status_code, 200, r.content)
        return r.data["fichier"]

    def test_adresse_brute_refusee_sans_connexion(self):
        self.assertEqual(APIClient().get(self.brut).status_code, 404)

    def test_api_renvoie_un_lien_signe(self):
        url = self.lien("eveque")
        self.assertIn("/media/documents/", url)
        self.assertIn("?j=", url)
        # Le lien fonctionne dans <img> ou un nouvel onglet, sans en-tête d'authentification
        r = APIClient().get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"%PDF-1.4 titre foncier")
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertIn("private", r["Cache-Control"])

    def test_signature_falsifiee_ou_detournee(self):
        url = self.lien("eveque")
        chemin, jeton = url.split("?j=")
        self.assertEqual(APIClient().get(f"{chemin}?j={jeton[:-3]}abc").status_code, 404)
        # Une signature valide pour un fichier ne donne pas accès à un autre
        autre = "/media/" + self.piege.fichier.name
        self.assertEqual(APIClient().get(f"{autre}?j={jeton}").status_code, 404)

    def test_lien_expire(self):
        url = self.lien("eveque")
        time.sleep(1.2)
        with self.settings(FICHIERS_LIEN_MINUTES=0):
            self.assertEqual(APIClient().get(url).status_code, 404)

    def test_compte_desactive(self):
        url = self.lien("surintendant.gitega")
        get_user_model().objects.filter(username="surintendant.gitega").update(is_active=False)
        self.assertEqual(APIClient().get(url).status_code, 404)

    def test_hors_perimetre_pas_de_lien(self):
        # Un agent d'un autre district ou une autre organisation ne voit même pas la fiche
        for username in ("agent.burunga", "admin.rwanda"):
            self.assertEqual(self.client_pour(username).get(f"/api/documents/{self.doc.pk}/").status_code, 404, username)

    def test_bearer_sans_signature_controle_le_perimetre(self):
        self.assertEqual(self.client_pour("eveque").get(self.brut).status_code, 200)
        self.assertEqual(self.client_pour("surintendant.gitega").get(self.brut).status_code, 200)
        for username in ("agent.burunga", "admin.rwanda"):
            self.assertEqual(self.client_pour(username).get(self.brut).status_code, 404, username)

    def test_html_telecharge_jamais_affiche(self):
        r = APIClient().get(self.lien("eveque", self.piege))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r["Content-Disposition"].startswith("attachment"))
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")

    def test_chemins_pieges(self):
        c = self.client_pour("admin")
        for chemin in ("/media/../manage.py", "/media/documents/../../manage.py", "/media/inconnu/x.pdf"):
            self.assertEqual(c.get(chemin).status_code, 404, chemin)

    def test_sante_indique_la_version(self):
        from config.version import VERSION

        self.assertEqual(APIClient().get("/api/sante/").data["version"], VERSION)


class ReglagesProductionTests(Base):
    """La production refuse de démarrer avec des réglages dangereux."""

    def demarrer(self, **variables):
        env = {**os.environ, "DJANGO_DEBUG": "0", "DJANGO_SECRET_KEY": "x" * 50, "DJANGO_ALLOWED_HOSTS": "umurage.example.org",
               "DJANGO_SETTINGS_MODULE": "config.settings", **variables}
        return subprocess.run([sys.executable, "-c", "import django; django.setup()"], env=env,
                              cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True)

    def test_reglages_valides(self):
        self.assertEqual(self.demarrer().returncode, 0)

    def test_hote_obligatoire(self):
        for hotes in ("", "*"):
            r = self.demarrer(DJANGO_ALLOWED_HOSTS=hotes)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("DJANGO_ALLOWED_HOSTS", r.stderr)

    def test_cle_secrete_trop_courte(self):
        r = self.demarrer(DJANGO_SECRET_KEY="construction")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("DJANGO_SECRET_KEY", r.stderr)
