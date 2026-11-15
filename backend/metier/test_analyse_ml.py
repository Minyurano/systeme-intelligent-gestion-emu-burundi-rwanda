"""Tests 3.9 : analyse de la comparaison des églises par apprentissage automatique."""
from django.core.cache import cache

from core.tests import Base
from metier import analyse_ml


def ligne(i, indice, membres, biens, titres, risque, qualite):
    return {"id": i, "nom": f"Église {i}", "membres": membres, "biens": biens, "valeur": biens * 5e7,
            "valeur_par_membre": biens * 5e7 / membres, "beneficiaires": membres // 3, "qualite": qualite,
            "pct_titres": titres, "pct_a_risque": risque, "mauvais": 0, "ordres_ouverts": 0, "taux_recouvrement": None,
            "dons_par_membre": 1000, "taux_registre": 50, "indice": indice}


class AnalyseApiTests(Base):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_analyse_complete_paroisses(self):
        r = self.client_pour("eveque").get("/api/comparaison/analyse/?niveau=paroisse")
        self.assertEqual(r.status_code, 200, r.content)
        d = r.data
        self.assertTrue(d["disponible"])
        n = d["n"]
        self.assertGreaterEqual(n, 6)
        # Profils : chaque église est dans exactement un profil, avec un nom et une lecture
        noms = [m for p in d["profils"] for m in p["membres"]]
        self.assertEqual(len(noms), n)
        self.assertEqual(len(set(noms)), n)
        self.assertTrue(all(p["nom"] for p in d["profils"]))
        self.assertIn("texte", d["qualite_profils"])
        # Carte : un point par église, axes décrits en clair
        self.assertEqual(len(d["carte"]["points"]), n)
        self.assertTrue(d["carte"]["axes"]["x"]["texte"].startswith("Vers la droite"))
        self.assertGreater(d["carte"]["variance_totale"], 0)
        # Indice attendu, réseau de neurones et jumelles
        self.assertTrue(d["attendu"]["disponible"])
        self.assertTrue(all(0 <= l["attendu"] <= 100 for l in d["attendu"]["lignes"]))
        self.assertTrue(d["atypiques"]["disponible"])
        self.assertEqual(len(d["atypiques"]["lignes"]), n)
        for j in d["jumelles"]:
            self.assertGreaterEqual(j["modele"]["indice"], j["indice"] + 5)
            self.assertTrue(j["lecons"])
        self.assertTrue(d["resume"])
        self.assertEqual(len(d["methode"]), 5)

    def test_resultat_stable(self):
        c = self.client_pour("eveque")
        a = c.get("/api/comparaison/analyse/").data
        cache.clear()
        b = c.get("/api/comparaison/analyse/").data
        self.assertEqual(a["profils"], b["profils"])
        self.assertEqual(a["atypiques"]["lignes"], b["atypiques"]["lignes"])

    def test_districts_peu_nombreux(self):
        d = self.client_pour("eveque").get("/api/comparaison/analyse/?niveau=district").data
        self.assertTrue(d["disponible"])
        self.assertEqual(d["fiabilite"]["niveau"], "faible")
        if not d["atypiques"]["disponible"]:
            self.assertIn("au moins 6", d["atypiques"]["raison"])
        self.assertTrue(all("Districts" in p["nom"] or p["nom"] == "Profil unique" for p in d["profils"]))

    def test_cloisonnement(self):
        """Le surintendant n'analyse que son district ; une autre organisation n'apparaît jamais."""
        sup = self.client_pour("surintendant.gitega").get("/api/comparaison/analyse/").data
        eveque = self.client_pour("eveque").get("/api/comparaison/analyse/").data
        self.assertLess(sup["n"], eveque["n"])
        rwanda = self.client_pour("admin.rwanda").get("/api/comparaison/analyse/").data
        ids_burundi = {p["id"] for p in eveque["carte"]["points"]}
        ids_rwanda = {p["id"] for p in (rwanda.get("carte") or {}).get("points", [])}
        self.assertFalse(ids_burundi & ids_rwanda)

    def test_anonyme_refuse(self):
        from rest_framework.test import APIClient

        self.assertEqual(APIClient().get("/api/comparaison/analyse/").status_code, 401)


class AnalyseMethodesTests(Base):
    """Les méthodes retrouvent une structure connue à l'avance."""

    def test_trois_groupes_et_une_eglise_atypique(self):
        lignes = []
        for i in range(6):   # bien gérées
            lignes.append(ligne(i, 90 + i % 3, 2000 + 50 * i, 4, 100, 0, 85 + i % 2))
        for i in range(6, 12):  # à accompagner
            lignes.append(ligne(i, 35 + i % 3, 2100 + 50 * i, 4, 0, 60, 60 + i % 2))
        for i in range(12, 18):  # intermédiaires
            lignes.append(ligne(i, 65 + i % 3, 2050 + 50 * i, 4, 50, 25, 72 + i % 2))
        # Église hors norme : énorme patrimoine, peu de membres
        lignes.append({**ligne(99, 70, 150, 40, 50, 25, 72), "beneficiaires": 90000})
        r = analyse_ml._analyser(lignes, "paroisse", 2026)
        groupes = {p["nom"]: p["membres"] for p in r["profils"]}
        self.assertGreaterEqual(len(groupes), 3)
        # Les églises bien gérées se retrouvent ensemble, dans le premier profil
        premier = r["profils"][0]["membres"]
        self.assertTrue({f"Église {i}" for i in range(6)} <= set(premier))
        self.assertTrue(r["profils"][-1]["faiblesses"])
        atypiques = [l["nom"] for l in r["atypiques"]["lignes"] if l["atypique"]]
        self.assertEqual(atypiques, ["Église 99"])
        # Une église à accompagner reçoit une jumelle de même contexte qui fait mieux, avec des leçons précises
        j = next(j for j in r["jumelles"] if j["nom"] == "Église 6")
        self.assertTrue(any("Terrains titrés" in l or "risque" in l for l in j["lecons"]))

    def test_trop_peu_d_entites(self):
        r = analyse_ml._analyser([ligne(1, 50, 100, 2, 0, 0, 70), ligne(2, 60, 120, 3, 50, 0, 75)], "paroisse", 2026)
        self.assertFalse(r["disponible"])
        self.assertIn("au moins 3", r["raison"])
