"""Tests des modules métier (python manage.py test metier)."""
import io
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient

from core.deuxfacteurs import code_totp
from core.models import District, Profil
from core.tests import MDP, Base
from finances.models import Transaction
from patrimoine.models import Bien, Document, Mouvement

from . import services, taches
from .models import Bail, Campagne, Demande, Echeance, Loyer, OrdreTravail, PlanMaintenance


class ApprobationsTests(Base):
    def setUp(self):
        super().setUp()
        self.git = District.objects.get(code="GIT", organisation__slug="emu-burundi")
        self.terrain = Bien.objects.filter(district=self.git, categorie="FON").first()

    def _cession(self, client):
        r = client.post("/api/demandes/", {"type": "CESSION", "titre": "Vente parcelle", "bien": self.terrain.pk,
                                           "district": self.git.pk, "montant": 30_000_000}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        return r.data

    def test_circuit_complet_de_cession(self):
        sur, ev = self.client_pour("surintendant.gitega"), self.client_pour("eveque")
        tr = self.client_pour("tresorier")
        d = self._cession(tr)
        self.assertEqual(d["circuit"], ["SURINTENDANT", "EVEQUE"])
        # L'évêque ne peut pas sauter le niveau du surintendant
        self.assertEqual(ev.post(f"/api/demandes/{d['id']}/valider/", {}, format="json").status_code, 403)
        self.assertEqual(sur.post(f"/api/demandes/{d['id']}/valider/", {"commentaire": "OK"}, format="json").status_code, 200)
        r = ev.post(f"/api/demandes/{d['id']}/valider/", {}, format="json")
        self.assertEqual(r.data["statut"], "APPROUVEE")
        r = ev.post(f"/api/demandes/{d['id']}/executer/", {}, format="json")
        self.assertEqual(r.data["statut"], "EXECUTEE", r.content)
        self.terrain.refresh_from_db()
        self.assertIsNotNone(self.terrain.date_sortie)
        self.assertTrue(Mouvement.objects.filter(bien=self.terrain, type="CESSION").exists())
        self.assertTrue(Transaction.objects.filter(bien=self.terrain, categorie="CESSION", montant=30_000_000).exists())
        codes = [b["code"] for b in ev.get("/api/biens/?page_size=500").data["results"]]
        self.assertNotIn(self.terrain.code, codes)  # sorti de l'inventaire actif
        self.assertEqual(ev.get(f"/api/biens/{self.terrain.pk}/").status_code, 200)  # mais toujours consultable

    def test_separation_des_taches(self):
        sur = self.client_pour("surintendant.gitega")
        d = self._cession(sur)
        r = sur.post(f"/api/demandes/{d['id']}/valider/", {}, format="json")
        self.assertEqual(r.status_code, 403)  # personne ne valide sa propre demande

    def test_rejet_motive_obligatoire(self):
        d = self._cession(self.client_pour("tresorier"))
        sur = self.client_pour("surintendant.gitega")
        self.assertEqual(sur.post(f"/api/demandes/{d['id']}/valider/", {"decision": "REJETE"}, format="json").status_code, 400)
        r = sur.post(f"/api/demandes/{d['id']}/valider/", {"decision": "REJETE", "commentaire": "Terrain en litige"}, format="json")
        self.assertEqual(r.data["statut"], "REJETEE")

    def test_grosse_depense_remonte_a_la_direction(self):
        self.assertEqual(services.circuit_pour("DEPENSE", 100_000), ["SURINTENDANT", "TRESORIER"])
        self.assertEqual(services.circuit_pour("DEPENSE", 9_000_000), ["SURINTENDANT", "TRESORIER", "EVEQUE"])

    def test_transfert_change_le_district(self):
        bjm = District.objects.get(code="BJM", organisation__slug="emu-burundi")
        bien = Bien.objects.filter(district=self.git, categorie="EQP").first() or Bien.objects.filter(district=self.git).first()
        org = self.git.organisation
        agent = Profil.objects.get(user__username="tresorier")
        d = services.creer_demande(Demande(organisation=org, district=self.git, type="TRANSFERT", bien=bien, district_destination=bjm,
                                           titre="Transfert", demandeur=agent.user))
        services.decider(d, Profil.objects.get(user__username="surintendant.gitega"), "APPROUVE")
        ev = Profil.objects.get(user__username="eveque")
        services.decider(d, ev, "APPROUVE")
        services.executer(d, ev)
        bien.refresh_from_db()
        self.assertEqual(bien.district_id, bjm.pk)

    def test_cloisonnement_entre_organisations(self):
        self._cession(self.client_pour("tresorier"))
        rw = self.client_pour("admin.rwanda")
        self.assertEqual(rw.get("/api/demandes/").data["count"], 0)
        self.assertEqual(rw.get("/api/baux/").data, [])


class EcheancesTests(Base):
    def test_echeance_periodique_et_rappels(self):
        org = District.objects.get(code="GIT").organisation
        e = Echeance.objects.create(organisation=org, libelle="Assurance", type="ASSURANCE", date=date.today() + timedelta(days=5),
                                    periodicite_mois=12)
        with mock.patch("metier.services.envoyer") as envoi:
            n1 = services.envoyer_rappels()
            n2 = services.envoyer_rappels()
        self.assertGreaterEqual(n1, 1)
        e.refresh_from_db()
        self.assertTrue(e.rappel_j7)
        self.assertEqual(Echeance.objects.filter(pk=e.pk, rappel_j7=True).count(), 1)
        self.assertLess(n2, n1 + 1)  # pas de second rappel pour la même échéance
        r = self.client_pour("tresorier").post(f"/api/echeances/{e.pk}/faite/", {}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["suivante"]["date"], (e.date.replace(year=e.date.year + 1)).isoformat())


class BauxTests(Base):
    def test_bail_loyers_et_paiement(self):
        tr = self.client_pour("tresorier")
        bien = Bien.objects.filter(district__code="BJM", categorie="IMM").first()
        debut = (date.today().replace(day=1) - timedelta(days=95)).replace(day=1)
        r = tr.post("/api/baux/", {"bien": bien.pk, "locataire": "Test SARL", "loyer_mensuel": 200000, "date_debut": debut.isoformat(),
                                   "jour_echeance": 5}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        loyers = tr.get(f"/api/loyers/?bail={r.data['id']}").data
        self.assertGreaterEqual(len(loyers), 3)
        ancien = sorted(loyers, key=lambda l: l["periode"])[0]
        self.assertEqual(ancien["statut"], "IMPAYE")
        p = tr.post(f"/api/loyers/{ancien['id']}/payer/", {"montant": 200000, "canal": "MOBILE", "reference": "LUMI42"}, format="json")
        self.assertEqual(p.data["statut"], "PAYE", p.content)
        t = Transaction.objects.get(pk=p.data["transaction"])
        self.assertEqual((t.categorie, t.sens, t.bien_id), ("LOYER", "RECETTE", bien.pk))
        self.assertEqual(self.client_pour("agent.burunga").post(f"/api/loyers/{ancien['id']}/payer/", {}, format="json").status_code, 403)


class MaintenanceTests(Base):
    def test_ordre_termine_alimente_historique_et_finances(self):
        bien = Bien.objects.filter(district__code="GIT").first()
        plan = PlanMaintenance.objects.create(bien=bien, libelle="Vidange", periodicite_mois=6, prochaine_date=date.today())
        n = taches.ordres_depuis_plans(date.today())
        self.assertGreaterEqual(n, 1)
        self.assertEqual(taches.ordres_depuis_plans(date.today()), 0)  # idempotent
        ot = OrdreTravail.objects.get(plan=plan)
        r = self.client_pour("tresorier").post(f"/api/ordres-travail/{ot.pk}/terminer/",
                                                          {"cout_reel": 300000, "rapport": "Fait", "enregistrer_depense": True}, format="json")
        self.assertEqual(r.data["statut"], "TERMINE", r.content)
        self.assertTrue(Mouvement.objects.filter(bien=bien, description__contains=f"OT-{ot.pk}").exists())
        self.assertTrue(Transaction.objects.filter(pk=r.data["transaction"], categorie="MAINTENANCE").exists())
        plan.refresh_from_db()
        self.assertGreater(plan.prochaine_date, date.today())

    def test_risque_devient_action(self):
        b = Bien.objects.filter(district__organisation__slug="emu-burundi").first()
        OrdreTravail.objects.filter(bien=b).delete()
        b.score_risque = 92
        b.save()
        taches.ordres_depuis_risques(date.today())
        ot = OrdreTravail.objects.get(bien=b, origine="RISQUE")
        self.assertEqual(ot.priorite, "URGENTE")
        self.assertEqual(taches.ordres_depuis_risques(date.today()), 0)


class ComptabiliteTests(Base):
    def test_registre_amortissement_lineaire(self):
        from .comptabilite import ligne_registre
        b = Bien(code="T-1", nom="Moto", categorie="VEH", valeur_acquisition=Decimal(6_000_000), duree_vie_ans=5,
                 date_acquisition=date(2024, 1, 1), district=District.objects.first())
        l = ligne_registre(b, 2025)
        self.assertEqual(l["dotation_exercice"], 1_200_000)
        self.assertEqual(l["amortissements_cumules"], 2_400_000)
        self.assertEqual(l["valeur_nette_comptable"], 3_600_000)
        t = Bien(code="T-2", nom="Terrain", categorie="FON", valeur_acquisition=Decimal(9_000_000), date_acquisition=date(2000, 1, 1),
                 district=District.objects.first())
        self.assertFalse(ligne_registre(t, 2025)["amortissable"])
        r = self.client_pour("tresorier").get("/api/compta/registre/?annee=2025&export=csv")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Valeur nette comptable", r.content.decode("utf-8"))
        self.assertEqual(self.client_pour("agent.burunga").get("/api/compta/registre/").status_code, 403)

    def test_cloture_bloque_les_ecritures(self):
        tr = self.client_pour("tresorier")
        annee = date.today().year - 1
        self.assertEqual(tr.post("/api/clotures/", {"annee": date.today().year}, format="json").status_code, 400)
        self.assertEqual(tr.post("/api/clotures/", {"annee": annee}, format="json").status_code, 201)
        git = District.objects.get(code="GIT", organisation__slug="emu-burundi")
        r = tr.post("/api/transactions/", {"date": f"{annee}-06-01", "sens": "DEPENSE", "categorie": "ACHAT", "montant": 1000,
                                           "district": git.pk}, format="json")
        self.assertEqual(r.status_code, 400)
        ancienne = Transaction.objects.filter(district=git, date__year=annee).first()
        if ancienne:
            self.assertEqual(tr.delete(f"/api/transactions/{ancienne.pk}/").status_code, 400)
        self.assertEqual(tr.get(f"/api/budgets/suivi/?annee={date.today().year}").status_code, 200)

    def test_rapprochement_par_reference(self):
        git = District.objects.get(code="GIT", organisation__slug="emu-burundi")
        t = Transaction.objects.create(date=date.today(), sens="RECETTE", categorie="DON", montant=Decimal(77_777), district=git,
                                       canal="MOBILE", reference_externe="ECO-998877")
        csv = "date;montant;reference;libelle\n" + f"{date.today():%d/%m/%Y};77 777;ECO-998877;Don\n" + "01/01/2020;5;XX;Frais\n"
        r = self.client_pour("tresorier").post("/api/compta/rapprochement/",
                                               {"fichier": SimpleUploadedFile("releve.csv", csv.encode())}, format="multipart")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["rapprochees"], 1)
        self.assertEqual(len(r.data["lignes_sans_correspondance"]), 1)
        t.refresh_from_db()
        self.assertTrue(t.rapprochee)


class InventaireTests(Base):
    def test_campagne_scan_ecarts_et_cloture(self):
        sur = self.client_pour("surintendant.gitega")
        r = sur.post("/api/campagnes/", {"nom": "Inventaire test"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        cid = r.data["id"]
        biens = list(Bien.objects.filter(district__code="GIT", district__organisation__slug="emu-burundi", date_sortie__isnull=True).order_by("code"))
        etat_nouveau = "MAUVAIS" if biens[0].etat != "MAUVAIS" else "BON"
        self.assertEqual(sur.post(f"/api/campagnes/{cid}/scanner/", {"code": biens[0].code, "etat_constate": etat_nouveau}, format="json").status_code, 200)
        sur.post(f"/api/campagnes/{cid}/scanner/", {"code": biens[1].code, "trouve": False}, format="json")
        e = sur.get(f"/api/campagnes/{cid}/ecarts/").data
        self.assertEqual(e["vus"], 2)
        self.assertEqual(len(e["non_vus"]), len(biens) - 2)
        self.assertEqual(len(e["etats_differents"]), 1)
        self.assertEqual(sur.post(f"/api/campagnes/{cid}/scanner/", {"code": "INEXISTANT"}, format="json").status_code, 400)
        c = sur.post(f"/api/campagnes/{cid}/cloturer/", {"appliquer_etats": True}, format="json")
        self.assertEqual(c.data["statut"], "CLOTUREE", c.content)
        biens[0].refresh_from_db()
        self.assertEqual(biens[0].etat, etat_nouveau)
        self.assertTrue(OrdreTravail.objects.filter(bien=biens[1], origine="INVENTAIRE").exists())

    def test_documents_obligatoires(self):
        veh = Bien.objects.filter(categorie="VEH", district__organisation__slug="emu-burundi").first()
        r = self.client_pour("eveque").get("/api/documents-manquants/").data
        self.assertTrue(any(m["bien"] == veh.pk and m["document"] == "CARTE_GRISE" for m in r["manquants"]))
        Document.objects.create(organisation=veh.district.organisation, bien=veh, titre="Carte grise", type="CARTE_GRISE")
        r = self.client_pour("eveque").get("/api/documents-manquants/").data
        self.assertFalse(any(m["bien"] == veh.pk and m["document"] == "CARTE_GRISE" for m in r["manquants"]))


class ExploitationTests(Base):
    def test_double_authentification(self):
        c = self.client_pour("tresorier")
        secret = c.post("/api/2fa/activer/").data["secret"]
        self.assertEqual(c.post("/api/2fa/confirmer/", {"code": "000000"}, format="json").status_code, 400)
        self.assertEqual(c.post("/api/2fa/confirmer/", {"code": code_totp(secret)}, format="json").status_code, 200)
        anonyme = APIClient()
        r = anonyme.post("/api/auth/token/", {"username": "tresorier", "password": MDP}, format="json")
        self.assertEqual(r.status_code, 401)
        self.assertTrue(r.data["otp_requis"])
        r = anonyme.post("/api/auth/token/", {"username": "tresorier", "password": MDP, "code": code_totp(secret)}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_sante(self):
        r = APIClient().get("/api/sante/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.data["base"])

    def test_sauvegarde_puis_restauration(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp + "/media"):
            call_command("sauvegarder", dossier=tmp, stdout=io.StringIO())
            archive = next(Path(tmp).glob("umurage_*.zip"))
            nb = Bien.objects.count()
            Bien.objects.filter(pk=Bien.objects.order_by("pk").last().pk).delete()
            self.assertEqual(Bien.objects.count(), nb - 1)
            call_command("restaurer", str(archive), oui=True, stdout=io.StringIO())
            self.assertEqual(Bien.objects.count(), nb)

    def test_taches_quotidiennes(self):
        bilan = taches.executer_tout()
        self.assertIn("rappels_envoyes", bilan)
        self.assertEqual(self.client_pour("tresorier").post("/api/taches/executer/").status_code, 403)
        self.assertEqual(self.client_pour("admin").post("/api/taches/executer/").status_code, 200)


class ComparaisonTests(Base):
    def test_comparaison_paroisses_et_districts(self):
        ev = self.client_pour("eveque")
        p = ev.get("/api/comparaison/?niveau=paroisse").data
        self.assertGreater(len(p["lignes"]), 3)
        self.assertEqual([l["rang"] for l in p["lignes"]], list(range(1, len(p["lignes"]) + 1)))
        self.assertTrue(all(l["indice"] is None or 0 <= l["indice"] <= 100 for l in p["lignes"]))
        d = ev.get("/api/comparaison/?niveau=district").data
        self.assertEqual(len(d["lignes"]), District.objects.filter(organisation__slug="emu-burundi").count())
        self.assertIn("solde", d["lignes"][0])
        # Un surintendant ne compare que les églises de son district, et une autre organisation ne voit rien du Burundi
        sur = self.client_pour("surintendant.gitega").get("/api/comparaison/?niveau=paroisse").data
        self.assertTrue(sur["lignes"] and all(l["district"] == "Gitega" for l in sur["lignes"]))
        rw = self.client_pour("admin.rwanda").get("/api/comparaison/?niveau=district").data
        self.assertTrue(all(l["nom"] not in ("Gitega", "Bujumbura") for l in rw["lignes"]))

    def test_compteurs_de_gravite(self):
        c = self.client_pour("tresorier").get("/api/metier/compteurs/").data
        for k in ("echeances_retard", "ordres_critiques", "loyers_impayes_anciens"):
            self.assertIn(k, c)


class RegistreMembresTests(Base):
    def setUp(self):
        super().setUp()
        from core.models import Paroisse
        self.p_git = Paroisse.objects.filter(district__code="GIT", district__organisation__slug="emu-burundi").first()
        self.p_brg = Paroisse.objects.filter(district__code="BRG", district__organisation__slug="emu-burundi").first()

    def _fiche(self, client, paroisse, **extra):
        corps = {"paroisse": paroisse.pk, "nom": "niyonzima", "prenom": "esther", "sexe": "F", "date_naissance": "1990-04-12",
                 "statut": "BAPTISE", "date_bapteme": "2004-08-01", **extra}
        return client.post("/api/registre/", corps, format="json")

    def test_numero_officiel_et_mise_en_forme(self):
        r = self._fiche(self.client_pour("surintendant.gitega"), self.p_git)
        self.assertEqual(r.status_code, 201, r.content)
        self.assertRegex(r.data["numero"], rf"^GIT-{date.today().year}-\d{{5}}$")
        self.assertEqual((r.data["nom"], r.data["prenom"]), ("NIYONZIMA", "Esther"))
        r2 = self._fiche(self.client_pour("surintendant.gitega"), self.p_git, nom="Bizimana", prenom="Eric", sexe="H")
        self.assertEqual(int(r2.data["numero"][-5:]), int(r.data["numero"][-5:]) + 1)

    def test_doublon_signale_puis_confirme(self):
        sur = self.client_pour("surintendant.gitega")
        self.assertEqual(self._fiche(sur, self.p_git).status_code, 201)
        r = self._fiche(sur, self.p_git)
        self.assertEqual(r.status_code, 400)
        self.assertIn("doublon", r.data)
        self.assertEqual(self._fiche(sur, self.p_git, confirmer_doublon=True).status_code, 201)

    def test_controles_de_dates(self):
        r = self._fiche(self.client_pour("surintendant.gitega"), self.p_git, date_bapteme="1980-01-01")
        self.assertEqual(r.status_code, 400)
        self.assertIn("date_bapteme", r.data)

    def test_cloisonnement_par_district(self):
        sur = self.client_pour("surintendant.gitega")
        self.assertEqual(self._fiche(sur, self.p_brg).status_code, 403)  # pas son district
        ag = self.client_pour("agent.burunga")
        self.assertEqual(self._fiche(ag, self.p_brg, nom="Minani").status_code, 201)
        numeros = [m["numero"] for m in sur.get("/api/registre/?page_size=500").data["results"]]
        self.assertFalse(any(n.startswith("BRG-") for n in numeros))

    def test_une_fiche_ne_se_supprime_pas_et_statistiques(self):
        sur = self.client_pour("surintendant.gitega")
        m = self._fiche(sur, self.p_git).data
        self.assertEqual(sur.delete(f"/api/registre/{m['id']}/").status_code, 403)
        self.assertEqual(self.client_pour("tresorier").post("/api/registre/", {}, format="json").status_code, 403)
        s = self.client_pour("eveque").get("/api/registre/statistiques/").data
        self.assertGreaterEqual(s["actifs"], 1)
        self.assertGreaterEqual(s["femmes"], 1)
        self.assertTrue(any(e["id"] == self.p_git.pk and e["inscrits"] >= 1 for e in s["eglises"]))


class StatistiquesEgliseTests(Base):
    def test_tableau_complet_et_cloisonne(self):
        ev = self.client_pour("eveque").get("/api/statistiques-eglise/")
        self.assertEqual(ev.status_code, 200, ev.content)
        d = ev.data
        self.assertEqual(len(d["membres"]["croissance"]), 12)
        self.assertEqual(len(d["finances"]), 12)
        self.assertGreater(len(d["districts"]), 1)
        cles = [x["cle"] for x in d["annee_comparee"]]
        self.assertIn("recettes", cles)
        self.assertIn("solde", cles)
        # Un surintendant ne voit que son district, même s'il en demande un autre
        autre = District.objects.filter(organisation__slug="emu-burundi").exclude(code="GIT").first()
        sur = self.client_pour("surintendant.gitega").get(f"/api/statistiques-eglise/?district={autre.pk}").data
        self.assertEqual([x["code"] for x in sur["districts"]], ["GIT"])

    def test_comparaison_a_date_egale(self):
        from .statistiques import statistiques
        from core.securite import profil_de
        from django.contrib.auth.models import User
        d = statistiques(profil_de(User.objects.get(username="eveque")))
        rec = next(x for x in d["annee_comparee"] if x["cle"] == "recettes")
        self.assertEqual(rec["ecart"], rec["actuel"] - rec["precedent"])
