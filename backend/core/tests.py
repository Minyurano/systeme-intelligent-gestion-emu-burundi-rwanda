"""Tests de bout en bout de l'API UMURAGE (python manage.py test)."""
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import District
from iot.models import Alerte, Capteur
from patrimoine.models import Bien

MDP = "umurage2026"


class Base(TestCase):
    """Données de démonstration chargées une fois, et connexion par identifiant."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def setUp(self):
        cache.clear()  # remet à zéro les limites de tentatives de connexion entre les tests

    def client_pour(self, username):
        c = APIClient()
        r = c.post("/api/auth/token/", {"username": username, "password": MDP}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return c


class ApiUmurageTests(Base):
    def test_authentification_obligatoire(self):
        self.assertEqual(APIClient().get("/api/biens/").status_code, 401)

    def test_eveque_voit_tout(self):
        r = self.client_pour("eveque").get("/api/biens/?page_size=200")
        self.assertEqual(r.data["count"], Bien.objects.filter(district__organisation__slug="emu-burundi").count())

    def test_surintendant_limite_a_son_district(self):
        c = self.client_pour("surintendant.gitega")
        r = c.get("/api/biens/")
        self.assertTrue(r.data["count"] > 0)
        self.assertTrue(all(b["district_nom"] == "Gitega" for b in r.data["results"]))
        autre = Bien.objects.exclude(district__code="GIT").first()
        self.assertEqual(c.get(f"/api/biens/{autre.pk}/").status_code, 404)

    def test_agent_ne_peut_pas_ecrire_ailleurs(self):
        c = self.client_pour("agent.burunga")
        brg, git = District.objects.get(code="BRG", organisation__slug="emu-burundi"), District.objects.get(code="GIT")
        donnees = {"nom": "Tables de l'église", "categorie": "EQP", "valeur_acquisition": 500000,
                   "date_acquisition": "2025-01-10", "quantite": 10}
        self.assertEqual(c.post("/api/biens/", {**donnees, "district": git.pk}, format="json").status_code, 403)
        r = c.post("/api/biens/", {**donnees, "district": brg.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.data["code"].startswith("BRG-EQP-"))
        bien = Bien.objects.get(pk=r.data["id"])
        self.assertIsNotNone(bien.valeur_estimee)  # valorisé automatiquement

    def test_tresorier_ne_modifie_pas_l_inventaire(self):
        c = self.client_pour("tresorier")
        b = Bien.objects.first()
        self.assertEqual(c.patch(f"/api/biens/{b.pk}/", {"nom": "x"}, format="json").status_code, 403)

    def test_journal_audit(self):
        c = self.client_pour("admin")
        b = Bien.objects.first()
        c.patch(f"/api/biens/{b.pk}/", {"etat": "MAUVAIS"}, format="json")
        r = c.get("/api/journal/")
        self.assertEqual(r.data["results"][0]["action"], "MODIFICATION")
        self.assertEqual(self.client_pour("agent.burunga").get("/api/journal/").status_code, 403)
        # Chaîne d'empreintes : intacte, puis cassée par une falsification directe en base
        self.assertTrue(c.get("/api/journal/verifier/").data["intact"])
        from core.models import JournalAction
        JournalAction.objects.filter(pk=r.data["results"][0]["id"]).update(objet_libelle="falsifié")
        self.assertFalse(c.get("/api/journal/verifier/").data["intact"])

    def test_tableau_de_bord_et_carte(self):
        c = self.client_pour("eveque")
        r = c.get("/api/tableau-de-bord/")
        self.assertGreater(r.data["kpi"]["valeur_totale"], 0)
        self.assertEqual(len(r.data["objectif_sante_2030"]), 5)
        self.assertTrue(len(c.get("/api/carte/").data) > 40)

    def test_analyse_bien(self):
        c = self.client_pour("eveque")
        terrain = Bien.objects.filter(categorie="FON").first()
        r = c.get(f"/api/biens/{terrain.pk}/analyse/")
        self.assertIn("Modèle ML", r.data["valorisation"]["methode"])
        self.assertTrue(r.data["valorisation"]["facteurs"])
        self.assertEqual(c.get(f"/api/biens/{terrain.pk}/qrcode/")["Content-Type"], "image/png")
        self.assertIn("text/csv", c.get("/api/biens/export/")["Content-Type"])

    def test_anomalies_et_previsions(self):
        c = self.client_pour("tresorier")
        r = c.get("/api/transactions/?est_anomalie=true")
        self.assertGreaterEqual(r.data["count"], 4)
        s = c.get("/api/transactions/synthese/")
        self.assertEqual(len(s.data["prevision"]["prevision"]), 6)

    def test_ingestion_iot(self):
        c = APIClient()
        mesure = {"capteur": "FOR-KAY-NIV", "valeur": 1.2}
        self.assertEqual(c.post("/api/iot/ingestion/", mesure, format="json").status_code, 401)
        r = c.post("/api/iot/ingestion/", mesure, format="json", HTTP_X_API_KEY="umurage-iot-demo-key")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Alerte.objects.filter(capteur__code="FOR-KAY-NIV", resolue=False).exists())
        self.assertEqual(Capteur.objects.get(code="FOR-KAY-NIV").derniere_valeur, 1.2)

    def test_assistant(self):
        c = self.client_pour("eveque")
        r = c.post("/api/ia/assistant/", {"question": "Qui a financé le forage de Muyange ?"}, format="json")
        self.assertIn("UMCOR", r.data["reponse"])
        self.assertTrue(r.data["sources"])

    def test_portail_public_sans_donnees_sensibles(self):
        r = APIClient().get("/api/public/")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.data["chiffres"]["forages"], 0)
        self.assertNotIn("transactions", str(r.data).lower())


class MultiOrganisationsTests(Base):
    """Une organisation ne voit, ne modifie et n'interroge jamais les données d'une autre."""

    def test_cloisonnement_lecture(self):
        rw = self.client_pour("admin.rwanda")
        noms = [b["nom"] for b in rw.get("/api/biens/").data["results"]]
        self.assertTrue(noms and all("Burundi" not in n and "Gitega" not in n for n in noms))
        bien_burundi = Bien.objects.filter(district__organisation__slug="emu-burundi").first()
        self.assertEqual(rw.get(f"/api/biens/{bien_burundi.pk}/").status_code, 404)
        self.assertEqual(rw.get("/api/moi/").data["organisation"]["devise"], "RWF")
        self.assertEqual(len(rw.get("/api/districts/").data), 3)
        self.assertEqual(rw.get("/api/recherche/?q=Gitega").data, [])

    def test_cloisonnement_ecriture(self):
        rw = self.client_pour("admin.rwanda")
        git = District.objects.get(code="GIT")
        r = rw.post("/api/biens/", {"nom": "Intrus", "categorie": "EQP", "district": git.pk, "valeur_acquisition": 1}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_assistant_cloisonne(self):
        rw = self.client_pour("admin.rwanda")
        r = rw.post("/api/ia/assistant/", {"question": "Qui a financé le forage de Muyange ?"}, format="json")
        self.assertNotIn("UMCOR", r.data["reponse"])

    def test_inscription_nouvelle_organisation(self):
        r = APIClient().post("/api/inscription/", {
            "nom": "Église de test", "sigle": "EDT", "pays": "Kenya", "devise": "kes", "taux_usd": 130, "langue": "en",
            "districts": ["Nairobi", "Mombasa"], "admin_prenom": "Ada", "admin_nom": "Test", "admin_email": "ada@example.org",
            "admin_identifiant": "ada.test", "admin_mot_de_passe": "unMotDePasse!2026",
        }, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        c = self.client_pour_mdp("ada.test", "unMotDePasse!2026")
        self.assertEqual(c.get("/api/biens/").data["count"], 0)
        self.assertEqual(c.get("/api/moi/").data["organisation"]["devise"], "KES")
        self.assertEqual([d["code"] for d in c.get("/api/districts/").data], ["MOM", "NAI"])

    def client_pour_mdp(self, username, mdp):
        c = APIClient()
        r = c.post("/api/auth/token/", {"username": username, "password": mdp}, format="json")
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return c


class TerrainEtInteroperabiliteTests(Base):
    def test_whatsapp_nouveau_bien_puis_validation(self):
        agent = self.client_pour("agent.burunga")
        r = agent.post("/api/declarations/simuler/", {"telephone": "+257 79 00 00 01",
                                                     "texte": "Nouveau forage à Gahambwe, bon état, financé par UMCOR, 20 000 000 BIF"}, format="multipart")
        d = r.data["declaration"]
        self.assertEqual(d["interpretation"]["categorie"], "INF")
        self.assertEqual(d["interpretation"]["valeur_acquisition"], 20_000_000)
        # L'agent ne peut pas valider ; le surintendant de son district non plus (autre district) ; la direction oui
        self.assertEqual(agent.post(f"/api/declarations/{d['id']}/valider/").status_code, 403)
        r = self.client_pour("eveque").post(f"/api/declarations/{d['id']}/valider/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(Bien.objects.get(pk=r.data["bien"]).code.startswith("BRG-INF-"))

    def test_whatsapp_signalement_bien_existant(self):
        sup = self.client_pour("surintendant.gitega")
        r = sup.post("/api/declarations/simuler/", {"telephone": "+25779000002", "texte": "Le toit de l'école de Nyabugogo fuit, mauvais état"}, format="multipart")
        d = r.data["declaration"]
        existant = d["interpretation"]["bien_existant"]
        r = sup.post(f"/api/declarations/{d['id']}/valider/", {"mode": "mise_a_jour"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Bien.objects.get(pk=existant["id"]).etat, "MAUVAIS")

    def test_numero_inconnu(self):
        r = self.client_pour("admin").post("/api/declarations/simuler/", {"telephone": "+10000000", "texte": "forage"}, format="multipart")
        self.assertIsNone(r.data["declaration"])

    def test_import_excel_csv(self):
        c = self.client_pour("admin")
        csv = "Nom;Catégorie;District;Paroisse;État;Valeur\nForage importé;Forage;Bujumbura;Rohero;Bon;12 000 000\nInconnu;Terrain;Nulle part;;Bon;\n"
        r = c.post("/api/import/biens/", {"fichier": SimpleUploadedFile("i.csv", csv.encode())}, format="multipart")
        self.assertEqual((r.data["crees"], r.data["invalides"]), (1, 1))
        self.assertTrue(Bien.objects.filter(nom="Forage importé", district__code="BJM").exists())
        self.assertEqual(c.get("/api/import/modele/").status_code, 200)

    def test_export_iati_et_qualite(self):
        c = self.client_pour("eveque")
        xml = c.get("/api/export/iati/").content.decode()
        self.assertIn('<iati-activities version="2.03"', xml)
        self.assertIn('<recipient-country code="BI"', xml)
        q = c.get("/api/qualite/").data
        self.assertEqual(len(q["classement"]), 5)
        self.assertTrue(0 <= q["score_global"] <= 100)
        self.assertEqual(c.get("/api/export/transactions/").status_code, 200)

    def test_portail_public_par_organisation(self):
        r = APIClient().get("/api/public/?organisation=emu-rwanda")
        self.assertEqual(r.data["organisation"]["pays"], "Rwanda")
        self.assertEqual(APIClient().get("/api/public/?organisation=inexistante").status_code, 404)


class CacheTableauDeBordTests(Base):
    """Le cache accélère le tableau de bord sans jamais afficher de chiffres périmés ni mélanger les périmètres."""

    def test_nouveau_bien_visible_immediatement(self):
        c = self.client_pour("eveque")
        avant = c.get("/api/tableau-de-bord/").data["kpi"]["nb_biens"]
        self.assertEqual(c.get("/api/tableau-de-bord/").data["kpi"]["nb_biens"], avant)  # servi depuis le cache
        brg = District.objects.get(code="BRG", organisation__slug="emu-burundi")
        Bien.objects.create(nom="Groupe électrogène", categorie="EQP", district=brg, valeur_acquisition=1000)
        self.assertEqual(c.get("/api/tableau-de-bord/").data["kpi"]["nb_biens"], avant + 1)

    def test_mise_a_jour_en_masse_invalide_le_cache(self):
        from ia import predictions
        from patrimoine import cache_donnees
        c = self.client_pour("eveque")
        c.get("/api/tableau-de-bord/")
        v = cache_donnees.version()
        predictions.recalculer_risques()  # bulk_update : pas de signal, l'invalidation doit être explicite
        self.assertGreater(cache_donnees.version(), v)
        Bien.objects.filter(district__organisation__slug="emu-burundi").update(score_risque=99)
        cache_donnees.donnees_modifiees()
        r = c.get("/api/tableau-de-bord/").data
        self.assertEqual(r["kpi"]["risque_eleve"], r["kpi"]["nb_biens"])

    def test_cache_cloisonne_par_district_et_organisation(self):
        c_ev, c_sur = self.client_pour("eveque"), self.client_pour("surintendant.gitega")
        tout = c_ev.get("/api/tableau-de-bord/").data["kpi"]["nb_biens"]
        gitega = c_sur.get("/api/tableau-de-bord/").data["kpi"]["nb_biens"]
        self.assertLess(gitega, tout)
        self.assertEqual(Bien.objects.filter(district__code="GIT", district__organisation__slug="emu-burundi").count(), gitega)
        self.assertEqual(c_ev.get("/api/tableau-de-bord/").data["kpi"]["nb_biens"], tout)
        rw = self.client_pour("admin.rwanda").get("/api/tableau-de-bord/").data["kpi"]["nb_biens"]
        self.assertEqual(rw, Bien.objects.filter(district__organisation__slug="emu-rwanda").count())
        carte_sur = c_sur.get("/api/carte/").data
        self.assertTrue(all(p["district"] == "Gitega" for p in carte_sur))

    def test_portail_public_suit_les_projets(self):
        from patrimoine.models import Projet
        avant = APIClient().get("/api/public/?organisation=emu-burundi").data["chiffres"]["projets"]
        p = Projet.objects.filter(district__organisation__slug="emu-burundi", public=True).first()
        p.public = False
        p.save()
        self.assertEqual(APIClient().get("/api/public/?organisation=emu-burundi").data["chiffres"]["projets"], avant - 1)


class ModeDemonstrationTests(TestCase):
    """Les comptes de démonstration ne sont annoncés à l'interface qu'en mode démonstration."""

    def test_sante_indique_le_mode_demo(self):
        from django.test import override_settings

        client = APIClient()
        with override_settings(UMURAGE_DEMO=False):
            self.assertIs(client.get("/api/sante/").json()["demo"], False)
        with override_settings(UMURAGE_DEMO=True):
            self.assertIs(client.get("/api/sante/").json()["demo"], True)
