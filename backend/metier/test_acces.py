"""Accès des membres de l'Église : cloisonnement, droits des administrateurs, espace membre, demandes."""
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.models import JournalAction, Profil
from core.tests import MDP, Base
from patrimoine.models import Bien, Declaration

from .models import DemandeAcces, MembreEglise


def connecter(username, password):
    c = APIClient()
    r = c.post("/api/auth/token/", {"username": username, "password": password}, format="json")
    return c, r


class AccesMembresTests(Base):
    def membre(self):
        return self.client_pour("membre.kayero")

    def fiche_sans_acces(self, org="emu-burundi"):
        return (MembreEglise.objects.filter(paroisse__district__organisation__slug=org, statut__in=MembreEglise.ACTIFS,
                                            compte__isnull=True).order_by("numero").first())

    # ---------------------------------------------------------------- cloisonnement
    def test_membre_ne_voit_aucun_outil_de_gestion(self):
        c = self.membre()
        for url in ["biens/", "transactions/", "tableau-de-bord/", "registre/", "journal/", "compteurs/", "membres/", "carte/",
                    "declarations/", "acces-membres/", "demandes-acces/", "organisation/", "projets/", "documents/", "districts/",
                    "paroisses/", "echeances/", "baux/", "budgets/", "statistiques-eglise/", "qualite/", "recherche/?q=forage",
                    "export/transactions/", "compta/registre/", "metier/compteurs/", "capteurs/", "demandes/"]:
            self.assertEqual(c.get(f"/api/{url}").status_code, 403, url)
        self.assertEqual(c.post("/api/ia/assistant/", {"question": "Valeur du patrimoine ?"}, format="json").status_code, 403)
        self.assertEqual(c.post("/api/biens/", {"nom": "x"}, format="json").status_code, 403)

    def test_moi_et_espace_membre(self):
        c = self.membre()
        m = c.get("/api/moi/").data
        self.assertTrue(m["est_membre"])
        self.assertEqual(m["role"], "MEMBRE")
        self.assertIsNotNone(m["fiche"])
        r = c.get("/api/espace-membre/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["eglise"]["nom"], "Kayero")
        self.assertTrue(r.data["biens"])
        # Aucune donnée financière ni juridique sur les biens
        for b in r.data["biens"]:
            self.assertFalse({"valeur_acquisition", "valeur_estimee", "statut_juridique", "score_risque"} & set(b))
            self.assertTrue(Bien.objects.filter(pk=b["id"], district__code="BRG").exists())

    def test_le_personnel_n_a_pas_d_espace_membre(self):
        self.assertEqual(self.client_pour("eveque").get("/api/espace-membre/").status_code, 403)

    def test_identifiant_insensible_a_la_casse(self):
        _, r = connecter("MEMBRE.Kayero", MDP)
        self.assertEqual(r.status_code, 200)

    # ---------------------------------------------------------------- espace membre
    def test_membre_met_a_jour_ses_coordonnees(self):
        c = self.membre()
        r = c.patch("/api/espace-membre/coordonnees/", {"adresse": "Colline Gahambwe", "numero": "XXX", "statut": "DECEDE"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        fiche = User.objects.get(username="membre.kayero").fiche_membre
        self.assertEqual(fiche.adresse, "Colline Gahambwe")
        self.assertEqual(fiche.statut, "CONFESSANT")  # les champs officiels ne changent pas
        self.assertTrue(JournalAction.objects.filter(objet_id=str(fiche.pk), details__par_le_membre=True).exists())

    def test_signalement_du_membre_suit_le_circuit_de_validation(self):
        c = self.membre()
        ailleurs = Bien.objects.filter(district__code="GIT").first()
        r = c.post("/api/espace-membre/signalements/", {"texte": "Le toit fuit depuis la pluie", "bien": ailleurs.pk}, format="json")
        self.assertEqual(r.status_code, 400)
        bien = Bien.objects.filter(district__code="BRG", paroisse__nom="Kayero").first()
        r = c.post("/api/espace-membre/signalements/", {"texte": "Le toit fuit depuis la pluie de mardi", "bien": bien.pk}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        d = Declaration.objects.get(pk=r.data["signalement"]["id"])
        self.assertEqual(d.canal, "WEB")
        self.assertEqual(d.interpretation["bien_existant"]["id"], bien.pk)
        self.assertEqual(len(c.get("/api/espace-membre/signalements/").data), 1)
        # Le responsable du district le voit dans ses déclarations à valider
        liste = self.client_pour("agent.burunga").get("/api/declarations/?statut=EN_ATTENTE").data
        ids = [x["id"] for x in (liste["results"] if isinstance(liste, dict) else liste)]
        self.assertIn(d.pk, ids)

    # ---------------------------------------------------------------- administrateurs
    def test_seul_l_administrateur_gere_les_acces(self):
        for qui in ["eveque", "tresorier", "surintendant.gitega", "agent.burunga"]:
            self.assertEqual(self.client_pour(qui).get("/api/acces-membres/").status_code, 403, qui)
        self.assertEqual(self.client_pour("admin").get("/api/acces-membres/").status_code, 200)

    def test_administrateur_donne_l_acces_puis_premiere_connexion(self):
        admin = self.client_pour("admin")
        fiche = self.fiche_sans_acces()
        r = admin.post(f"/api/acces-membres/{fiche.pk}/accorder/", {}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["identifiant"], fiche.numero)
        c, jeton = connecter(fiche.numero.lower(), r.data["mot_de_passe"])
        self.assertEqual(jeton.status_code, 200)
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {jeton.data['access']}")
        self.assertTrue(c.get("/api/moi/").data["doit_changer_mdp"])
        r2 = c.post("/api/moi/mot-de-passe/", {"ancien": r.data["mot_de_passe"], "nouveau": "Ma-nouvelle-cle-2026"}, format="json")
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertFalse(c.get("/api/moi/").data["doit_changer_mdp"])
        profil = Profil.objects.get(user__username=fiche.numero)
        self.assertEqual(profil.role, "MEMBRE")
        self.assertEqual(profil.district_id, fiche.paroisse.district_id)

    def test_suspension_et_deces_coupent_l_acces(self):
        admin = self.client_pour("admin")
        fiche = self.fiche_sans_acces()
        mdp = admin.post(f"/api/acces-membres/{fiche.pk}/accorder/", {}, format="json").data["mot_de_passe"]
        admin.post(f"/api/acces-membres/{fiche.pk}/suspendre/", {}, format="json")
        self.assertEqual(connecter(fiche.numero, mdp)[1].status_code, 401)
        admin.post(f"/api/acces-membres/{fiche.pk}/reactiver/", {}, format="json")
        self.assertEqual(connecter(fiche.numero, mdp)[1].status_code, 200)
        fiche.refresh_from_db()
        fiche.statut = MembreEglise.Statut.DECEDE
        fiche.save()
        self.assertEqual(connecter(fiche.numero, mdp)[1].status_code, 401)
        self.assertEqual(admin.post(f"/api/acces-membres/{fiche.pk}/reactiver/", {}, format="json").status_code, 400)

    def test_retirer_l_acces_conserve_la_fiche(self):
        admin = self.client_pour("admin")
        fiche = self.fiche_sans_acces()
        admin.post(f"/api/acces-membres/{fiche.pk}/accorder/", {}, format="json")
        self.assertEqual(admin.post(f"/api/acces-membres/{fiche.pk}/retirer/", {}, format="json").status_code, 204)
        self.assertFalse(User.objects.filter(username=fiche.numero).exists())
        self.assertTrue(MembreEglise.objects.filter(pk=fiche.pk).exists())

    def test_cloisonnement_entre_organisations(self):
        fiche = self.fiche_sans_acces()
        r = self.client_pour("admin.rwanda").post(f"/api/acces-membres/{fiche.pk}/accorder/", {}, format="json")
        self.assertEqual(r.status_code, 404)

    def test_acces_en_groupe_pour_une_eglise_locale(self):
        admin = self.client_pour("admin")
        fiche = self.fiche_sans_acces()
        attendus = MembreEglise.objects.filter(paroisse=fiche.paroisse, statut__in=MembreEglise.ACTIFS, compte__isnull=True).count()
        r = admin.post("/api/acces-membres/accorder-groupe/", {"paroisse": fiche.paroisse_id}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        # Les mineurs sans accord parental et les fiches sans date de naissance sont mis de côté, avec leur raison
        self.assertEqual(r.data["nombre"] + len(r.data["ignores"]), attendus)
        self.assertTrue(all(i["raison"] in ("accord_parental_requis", "date_naissance_manquante") for i in r.data["ignores"]))
        self.assertEqual(admin.get("/api/acces-membres/statistiques/").status_code, 200)

    def test_le_compte_d_un_membre_ne_se_cree_pas_comme_un_responsable(self):
        r = self.client_pour("admin").post("/api/membres/", {"username": "fidele", "role": "MEMBRE", "mot_de_passe": "abcdefgh12"},
                                           format="json")
        self.assertEqual(r.status_code, 400)
        noms = [m["username"] for m in self.client_pour("admin").get("/api/membres/").data]
        self.assertNotIn("membre.kayero", noms)

    # ---------------------------------------------------------------- demandes d'accès
    def test_demande_publique_puis_accord(self):
        public = APIClient()
        self.assertTrue(any(o["slug"] == "emu-burundi" for o in public.get("/api/acces/organisations/").data))
        fiche = self.fiche_sans_acces()
        fiche.telephone = "+25779555111"
        fiche.save()
        r = public.post("/api/acces/demande/", {"organisation": "emu-burundi", "numero": fiche.numero.lower(),
                                               "nom": f"{fiche.prenom} {fiche.nom}", "telephone": "79 555 111"}, format="json")
        self.assertEqual(r.status_code, 201)
        d = DemandeAcces.objects.get(membre=fiche)
        self.assertTrue(d.verifiee)
        # Un numéro inconnu reçoit exactement la même réponse
        r2 = public.post("/api/acces/demande/", {"organisation": "emu-burundi", "numero": "XXX-0000", "nom": "Inconnu Total",
                                                "telephone": "+25761000000"}, format="json")
        self.assertEqual(r2.data, r.data)
        self.assertFalse(DemandeAcces.objects.get(telephone="+25761000000").verifiee)
        admin = self.client_pour("admin")
        r3 = admin.post(f"/api/demandes-acces/{d.pk}/accorder/", {}, format="json")
        self.assertEqual(r3.status_code, 200, r3.content)
        d.refresh_from_db()
        self.assertEqual(d.statut, "ACCORDEE")
        self.assertEqual(admin.post(f"/api/demandes-acces/{d.pk}/accorder/", {}, format="json").status_code, 400)

    def test_demandes_fermees_par_l_administrateur(self):
        self.client_pour("admin").patch("/api/organisation/", {"demandes_acces_ouvertes": False}, format="json")
        r = APIClient().post("/api/acces/demande/", {"organisation": "emu-burundi", "nom": "Jean Test", "telephone": "+25779000099"},
                             format="json")
        self.assertEqual(r.status_code, 400)

    def test_le_registre_ne_peut_pas_relier_une_fiche_a_un_compte(self):
        fiche = self.fiche_sans_acces()
        eveque = User.objects.get(username="eveque")
        c = self.client_pour("admin")
        c.patch(f"/api/registre/{fiche.pk}/", {"compte": eveque.pk}, format="json")
        fiche.refresh_from_db()
        self.assertIsNone(fiche.compte_id)
