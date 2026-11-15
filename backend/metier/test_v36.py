"""v3.6 : jetons en cookie HttpOnly, mot de passe oublié, règle des mineurs, dîmes et attestations."""
from datetime import date, timedelta
from unittest import mock

from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.jetons import COOKIE
from core.models import CodeReinitialisation, JournalAction, Organisation
from core.tests import MDP, Base
from finances.models import Transaction

from .models import AttestationAnnuelle, ClotureExercice, Contribution, MembreEglise


def navigateur(username, password=MDP):
    """Client qui se comporte comme l'application : cookie de rafraîchissement + en-tête X-Umurage."""
    c = APIClient()
    r = c.post("/api/auth/token/", {"username": username, "password": password}, format="json")
    return c, r


class JetonsTests(Base):
    def test_le_rafraichissement_n_est_plus_lisible_par_la_page(self):
        c, r = navigateur("eveque")
        self.assertEqual(r.status_code, 200)
        self.assertIn("access", r.data)
        self.assertNotIn("refresh", r.data)  # plus dans le corps : seulement dans le cookie
        cookie = r.cookies[COOKIE]
        self.assertTrue(cookie["httponly"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertEqual(cookie["path"], "/api/auth/")

    def test_rotation_et_reutilisation_refusee(self):
        c, _ = navigateur("eveque")
        ancien = c.cookies[COOKIE].value
        self.assertEqual(c.post("/api/auth/refresh/").status_code, 403)  # sans en-tête X-Umurage
        r = c.post("/api/auth/refresh/", HTTP_X_UMURAGE="1")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertNotEqual(c.cookies[COOKIE].value, ancien)  # rotation
        voleur = APIClient()
        voleur.cookies[COOKIE] = ancien
        self.assertEqual(voleur.post("/api/auth/refresh/", HTTP_X_UMURAGE="1").status_code, 401)  # ancien jeton révoqué

    def test_deconnexion_ferme_la_session(self):
        c, _ = navigateur("eveque")
        self.assertEqual(c.post("/api/auth/deconnexion/").status_code, 204)
        jeton = c.cookies[COOKIE].value
        autre = APIClient()
        autre.cookies[COOKIE] = jeton
        self.assertEqual(autre.post("/api/auth/refresh/", HTTP_X_UMURAGE="1").status_code, 401)

    def test_changer_de_mot_de_passe_ferme_les_autres_sessions(self):
        telephone, _ = navigateur("tresorier")
        ordinateur, r = navigateur("tresorier")
        ordinateur.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        r2 = ordinateur.post("/api/moi/mot-de-passe/", {"ancien": MDP, "nouveau": "Nouvelle-cle-2026!"}, format="json")
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertIn("access", r2.data)
        self.assertEqual(telephone.post("/api/auth/refresh/", HTTP_X_UMURAGE="1").status_code, 401)
        self.assertEqual(ordinateur.post("/api/auth/refresh/", HTTP_X_UMURAGE="1").status_code, 200)

    def test_suspension_d_un_membre_ferme_sa_session(self):
        c, _ = navigateur("membre.kayero")
        fiche = User.objects.get(username="membre.kayero").fiche_membre
        self.client_pour("admin").post(f"/api/acces-membres/{fiche.pk}/suspendre/", {}, format="json")
        self.assertEqual(c.post("/api/auth/refresh/", HTTP_X_UMURAGE="1").status_code, 401)


class MotDePasseOublieTests(Base):
    def demander(self, identifiant):
        envoyes = {}
        with mock.patch("core.mdp_oublie.envoyer_code", side_effect=lambda u, code: envoyes.update(code=code) or ["WhatsApp"]):
            r = APIClient().post("/api/auth/mot-de-passe-oublie/", {"identifiant": identifiant}, format="json")
        return r, envoyes.get("code")

    def test_reponse_identique_compte_existant_ou_non(self):
        r1, code = self.demander("membre.kayero")
        r2, rien = self.demander("personne.inconnue")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.data, r2.data)
        self.assertIsNotNone(code)
        self.assertIsNone(rien)
        self.assertNotIn(code, CodeReinitialisation.objects.get(user__username="membre.kayero").empreinte)

    def test_reinitialisation_complete(self):
        _, code = self.demander("MEMBRE.KAYERO")
        session, _ = navigateur("membre.kayero")
        r = APIClient().post("/api/auth/reinitialiser/", {"identifiant": "membre.kayero", "code": code, "nouveau": "Cantique-de-Kayero-7"},
                             format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(navigateur("membre.kayero", "Cantique-de-Kayero-7")[1].status_code, 200)
        self.assertEqual(session.post("/api/auth/refresh/", HTTP_X_UMURAGE="1").status_code, 401)  # ancienne session fermée
        # Un code ne sert qu'une fois
        r = APIClient().post("/api/auth/reinitialiser/", {"identifiant": "membre.kayero", "code": code, "nouveau": "Autre-chose-2026"},
                             format="json")
        self.assertEqual(r.status_code, 400)

    def test_cinq_essais_puis_code_invalide(self):
        _, code = self.demander("membre.kayero")
        faux = "000000" if code != "000000" else "111111"
        for _ in range(5):
            r = APIClient().post("/api/auth/reinitialiser/", {"identifiant": "membre.kayero", "code": faux, "nouveau": "Cantique-de-Kayero-7"},
                                 format="json")
            self.assertEqual(r.status_code, 400)
        r = APIClient().post("/api/auth/reinitialiser/", {"identifiant": "membre.kayero", "code": code, "nouveau": "Cantique-de-Kayero-7"},
                             format="json")
        self.assertEqual(r.status_code, 400)  # même le bon code ne marche plus

    def test_code_expire(self):
        _, code = self.demander("membre.kayero")
        CodeReinitialisation.objects.update(expire_le=date.today() - timedelta(days=1))
        r = APIClient().post("/api/auth/reinitialiser/", {"identifiant": "membre.kayero", "code": code, "nouveau": "Cantique-de-Kayero-7"},
                             format="json")
        self.assertEqual(r.status_code, 400)


class MineursTests(Base):
    def fiche(self, age, **extra):
        j = date.today()
        p = MembreEglise.objects.filter(paroisse__district__organisation__slug="emu-burundi").first().paroisse
        return MembreEglise.objects.create(paroisse=p, nom="MINEUR", prenom="Test", sexe="H", statut="BAPTISE",
                                           date_naissance=date(j.year - age, 1, 1) if age is not None else None, **extra)

    def test_mineur_sans_accord_refuse_puis_accepte_avec_accord(self):
        admin = self.client_pour("admin")
        f = self.fiche(13)
        r = admin.post(f"/api/acces-membres/{f.pk}/accorder/", {}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["code"], "accord_parental_requis")
        accord = {"nom": "Jean MINEUR", "lien": "Père", "confirme": True}
        r = admin.post(f"/api/acces-membres/{f.pk}/accorder/", {"accord_parental": accord}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        f.refresh_from_db()
        self.assertEqual(f.accord_parental_nom, "Jean MINEUR")
        self.assertTrue(JournalAction.objects.filter(objet_id=str(f.pk), details__accord_parental__lien="Père").exists())

    def test_majeur_et_date_manquante(self):
        admin = self.client_pour("admin")
        self.assertEqual(admin.post(f"/api/acces-membres/{self.fiche(30).pk}/accorder/", {}, format="json").status_code, 201)
        r = admin.post(f"/api/acces-membres/{self.fiche(None).pk}/accorder/", {}, format="json")
        self.assertEqual(r.data["code"], "date_naissance_manquante")

    def test_age_minimum_reglable_et_acces_groupe_ignore_les_mineurs(self):
        admin = self.client_pour("admin")
        self.assertEqual(admin.patch("/api/organisation/", {"age_minimum_acces": 5}, format="json").status_code, 400)
        admin.patch("/api/organisation/", {"age_minimum_acces": 18}, format="json")
        f = self.fiche(17)
        r = admin.post("/api/acces-membres/accorder-groupe/", {"ids": [f.pk, self.fiche(40).pk]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["nombre"], 1)
        self.assertEqual(r.data["ignores"][0]["raison"], "accord_parental_requis")


class ContributionsTests(Base):
    def esther(self):
        return User.objects.get(username="membre.kayero").fiche_membre

    def test_saisie_recu_et_comptabilite(self):
        c = self.client_pour("agent.burunga")
        r = c.post("/api/contributions/", {"membre": self.esther().pk, "type": "DIME", "montant": 25000}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        contrib = Contribution.objects.get(pk=r.data["id"])
        self.assertRegex(contrib.numero_recu, rf"^EMUBURUN-{date.today().year}-\d{{6}}$|^[A-Z]+-{date.today().year}-\d{{6}}$")
        self.assertEqual(contrib.transaction.categorie, Transaction.Categorie.DIME)
        self.assertEqual(contrib.transaction.montant, 25000)
        # Mobile Money sans référence refusé ; montant négatif refusé
        self.assertEqual(c.post("/api/contributions/", {"membre": self.esther().pk, "montant": 1000, "mode": "MOBILE"}, format="json").status_code, 400)
        self.assertEqual(c.post("/api/contributions/", {"membre": self.esther().pk, "montant": -5}, format="json").status_code, 400)

    def test_cloisonnement_district_et_organisation(self):
        agent = self.client_pour("surintendant.gitega")
        r = agent.post("/api/contributions/", {"membre": self.esther().pk, "montant": 5000}, format="json")  # Esther est à Burunga
        self.assertEqual(r.status_code, 403)
        liste = agent.get("/api/contributions/?page_size=500").data["results"]
        self.assertTrue(all(x["district_nom"] == "Gitega" for x in liste))
        rw = self.client_pour("admin.rwanda")
        self.assertEqual(rw.post("/api/contributions/", {"membre": self.esther().pk, "montant": 5000,
                                                         "paroisse": self.esther().paroisse_id}, format="json").status_code, 403)
        self.assertEqual(self.client_pour("membre.kayero").get("/api/contributions/").status_code, 403)

    def test_annulation_tracee_et_exercice_clos(self):
        agent = self.client_pour("agent.burunga")
        r = agent.post("/api/contributions/", {"membre": self.esther().pk, "montant": 7000}, format="json")
        pk = r.data["id"]
        self.assertEqual(agent.post(f"/api/contributions/{pk}/annuler/", {"motif": "Erreur de saisie"}, format="json").status_code, 403)
        tres = self.client_pour("tresorier")
        self.assertEqual(tres.post(f"/api/contributions/{pk}/annuler/", {"motif": "Erreur de saisie"}, format="json").status_code, 200)
        c = Contribution.objects.get(pk=pk)
        self.assertTrue(c.annulee)
        self.assertIsNone(c.transaction_id)
        # Exercice clôturé : plus d'annulation possible
        org = Organisation.objects.get(slug="emu-burundi")
        ancien = Contribution.objects.filter(organisation=org, annulee=False, date__year=date.today().year - 1).first()
        ClotureExercice.objects.create(organisation=org, annee=ancien.date.year)
        self.assertEqual(tres.post(f"/api/contributions/{ancien.pk}/annuler/", {"motif": "Test clôture"}, format="json").status_code, 400)

    def test_espace_membre_et_attestation_verifiable(self):
        m = self.client_pour("membre.kayero")
        annee = date.today().year - 1
        r = m.get(f"/api/espace-membre/contributions/?annee={annee}")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.data["nombre"], 10)
        self.assertTrue(all(x["paroisse"] == "Kayero" for x in r.data["contributions"]))
        att = m.post("/api/espace-membre/attestation/", {"annee": annee}, format="json")
        self.assertEqual(att.status_code, 201, att.content)
        self.assertTrue(att.data["definitive"])
        self.assertTrue(att.data["qr"].startswith("data:image/png;base64,"))
        # Les totaux par nature additionnent bien tout le relevé (pas une ligne par versement)
        self.assertEqual(sum(int(t["total"]) for t in att.data["par_type"]), int(att.data["total"]))
        self.assertEqual(len({t["type"] for t in att.data["par_type"]}), len(att.data["par_type"]))
        self.assertEqual(att.data["total"], r.data["total"])
        # Même relevé → même attestation (pas de doublon)
        self.assertEqual(m.post("/api/espace-membre/attestation/", {"annee": annee}, format="json").data["code"], att.data["code"])
        v = APIClient().get(f"/api/attestations/verifier/{att.data['code'].lower()}/")
        self.assertEqual(v.status_code, 200)
        self.assertTrue(v.data["valide"] and v.data["a_jour"])
        self.assertNotIn("lignes", v.data)
        self.assertEqual(v.data["membre"], "Esther N.")
        self.assertEqual(APIClient().get("/api/attestations/verifier/AAAA-BBBB-CCCC/").status_code, 404)
        # Une contribution annulée ensuite : l'ancienne attestation est signalée « pas à jour »
        c = Contribution.objects.filter(membre=self.esther(), date__year=annee, annulee=False).first()
        c.annulee = True
        c.save()
        self.assertFalse(APIClient().get(f"/api/attestations/verifier/{att.data['code']}/").data["a_jour"])
        self.assertEqual(AttestationAnnuelle.objects.filter(membre=self.esther()).count(), 1)

    def test_synthese(self):
        r = self.client_pour("tresorier").get(f"/api/contributions/synthese/?annee={date.today().year - 1}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["par_mois"]), 12)
        self.assertGreater(r.data["total"], 0)
        self.assertGreater(r.data["donateurs"], 10)
        self.assertEqual(sum(t["total"] for t in r.data["par_type"]), r.data["total"])
        self.assertEqual(sum(m["total"] for m in r.data["par_mois"]), r.data["total"])
