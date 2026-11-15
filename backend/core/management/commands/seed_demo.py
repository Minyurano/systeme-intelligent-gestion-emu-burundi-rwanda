"""
Charge un jeu de données de DÉMONSTRATION.

Les lieux, districts, projets et partenaires viennent du rapport institutionnel de
l'Église. Les montants, surfaces, dates, mesures de capteurs et transactions sont
FICTIFS : ils servent uniquement à montrer le fonctionnement du système et doivent
être remplacés par l'inventaire réel (phase 2 du projet).

Usage : python manage.py seed_demo [--reset]
"""
import math
import random
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import District, JournalAction, Organisation, Paroisse, Profil
from finances.models import Transaction
from ia import anomalies, predictions, valorisation
from ia.models import ComparableMarche, EntrainementModele
from iot.models import Alerte, Capteur, Mesure
from iot.services import verifier_seuils
from patrimoine.models import Bien, Declaration, Document, Mouvement, Projet

MOT_DE_PASSE = "umurage2026"

DISTRICTS = [
    # code, nom, siège, lat, lon, anciens districts rattachés
    ("BHM", "Buhumuza", "Cankuzo", -3.2186, 30.5528, "Cankuzo, Murehe, Murore, Kinyinya"),
    ("BRG", "Burunga", "Kayero", -3.9000, 30.0200, "Kayero"),
    ("BTN", "Butanyerera", "Ngozi", -2.9075, 29.8306, "Ngozi"),
    ("BJM", "Bujumbura", "Bujumbura", -3.3822, 29.3644, "Bujumbura, Buhonga"),
    ("GIT", "Gitega", "Gitega", -3.4271, 29.9246, "Gitega, Mweya"),
]

PAROISSES = {
    "GIT": [("Cathédrale Saint-Pierre", -3.4280, 29.9230), ("Nyabugogo", -3.4100, 29.9400), ("Mweya", -3.3900, 29.9700)],
    "BJM": [("Rohero", -3.3900, 29.3700), ("Muyange", -3.3300, 29.4100), ("Buhonga", -3.4300, 29.3800)],
    "BRG": [("Kayero", -3.9000, 30.0200), ("Gahambwe", -3.8600, 30.1000), ("Kumoso", -3.7000, 30.2500), ("Musenyi", -3.9500, 30.0800)],
    "BHM": [("Cankuzo", -3.2186, 30.5528), ("Murehe", -2.9800, 30.1500), ("Murore", -3.1500, 30.4000), ("Kinyinya", -3.4500, 30.3000)],
    "BTN": [("Ngozi", -2.9075, 29.8306)],
}

# district, paroisse, nom, catégorie, sous-type, état, juridique, surface, quantité, année, valeur acq. (BIF),
# durée de vie, financeur, ODD, bénéficiaires
BIENS = [
    ("GIT", "Cathédrale Saint-Pierre", "Cathédrale Saint-Pierre de Gitega", "IMM", "Église", "BON", "TITRE", 2400, 1, 1995, 850_000_000, 60, "", "", 0),
    ("GIT", "Cathédrale Saint-Pierre", "Bureaux de la Conférence Annuelle", "IMM", "Bureaux", "BON", "TITRE", 600, 1, 2008, 320_000_000, 50, "", "", 0),
    ("GIT", "Mweya", "Terrain de la future université de Mweya", "FON", "Terrain", "BON", "EN_COURS", 120_000, 1, 2019, 180_000_000, None, "", "4", 0),
    ("GIT", "Mweya", "Université théologique de Mweya", "IMM", "Université", "CONSTRUCTION", "TITRE", 3500, 1, 2025, 400_000_000, 60, "", "4", 0),
    ("GIT", "Nyabugogo", "École fondamentale de Nyabugogo", "IMM", "École", "BON", "TITRE", 1200, 1, 2012, 260_000_000, 50, "", "4", 640),
    ("GIT", "Nyabugogo", "Centre des Femmes Méthodistes Unies", "IMM", "Centre de formation", "BON", "TITRE", 350, 1, 2016, 95_000_000, 50, "", "5", 120),
    ("GIT", "Nyabugogo", "Machines à coudre — Centre des Femmes", "EQP", "Machine à coudre", "BON", "NA", None, 32, 2023, 19_200_000, 10, "Conférence", "5", 32),
    ("GIT", "Nyabugogo", "Église paroissiale de Nyabugogo", "IMM", "Église", "MOYEN", "TITRE", 900, 1, 1989, 210_000_000, 60, "", "", 0),
    ("GIT", "Nyabugogo", "Lycée Technique Sabine Ndoricimpa", "IMM", "Lycée technique", "BON", "TITRE", 2200, 1, 2019, 540_000_000, 50, "", "4", 480),
    ("GIT", "Cathédrale Saint-Pierre", "Véhicule tout-terrain de la Conférence", "VEH", "Véhicule 4x4", "MOYEN", "NA", None, 1, 2018, 145_000_000, 10, "", "", 0),
    ("GIT", "Cathédrale Saint-Pierre", "Groupe électrogène des bureaux", "EQP", "Groupe électrogène", "MAUVAIS", "NA", None, 1, 2014, 28_000_000, 12, "", "", 0),
    ("GIT", "Cathédrale Saint-Pierre", "Parc informatique des bureaux", "EQP", "Ordinateurs", "MOYEN", "NA", None, 12, 2021, 26_400_000, 6, "", "", 0),
    ("BRG", "Kayero", "Terrain de la station missionnaire de Kayero", "FON", "Terrain", "BON", "TITRE", 85_000, 1, 1938, 40_000_000, None, "", "", 0),
    ("BRG", "Kayero", "Église historique de Kayero (1938)", "IMM", "Église", "MOYEN", "TITRE", 750, 1, 1958, 120_000_000, 80, "", "", 0),
    ("BRG", "Kayero", "École d'infirmières de Kayero", "IMM", "École d'infirmières", "CONSTRUCTION", "TITRE", 1400, 1, 2024, 310_000_000, 50, "", "3,4", 0),
    ("BRG", "Kayero", "Forage de Kayero", "INF", "Forage", "BON", "NA", None, 1, 2021, 38_000_000, 25, "UMCOR", "6", 2800),
    ("BRG", "Kayero", "Champ de tournesol des femmes de Kayero", "AGR", "Champ de tournesol", "BON", "NA", 30_000, 1, 2022, 6_000_000, 6, "YAI", "2,5", 85),
    ("BRG", "Kayero", "Cheptel caprin des femmes de Kayero", "AGR", "Chèvres", "BON", "NA", None, 45, 2023, 6_750_000, 6, "YAI", "2,5", 45),
    ("BRG", "Kayero", "Machines à coudre du district", "EQP", "Machine à coudre", "BON", "NA", None, 7, 2024, 4_200_000, 10, "Conférence", "5", 7),
    ("BRG", "Kumoso", "Usine de transformation du tournesol de Kumoso", "INF", "Usine", "CONSTRUCTION", "NA", None, 1, 2025, 420_000_000, 25, "UMDA", "2", 0),
    ("BRG", "Kumoso", "Terrain de l'usine de Kumoso", "FON", "Terrain", "BON", "EN_COURS", 15_000, 1, 2024, 30_000_000, None, "UMDA", "", 0),
    ("BRG", "Gahambwe", "Centre de santé de Gahambwe", "IMM", "Centre de santé", "BON", "TITRE", 800, 1, 2015, 230_000_000, 50, "UMDA", "3", 9500),
    ("BRG", "Musenyi", "Site d'accueil humanitaire de Musenyi", "FON", "Terrain", "BON", "SANS_TITRE", 8_000, 1, 2024, 12_000_000, None, "", "10", 1200),
    ("BRG", "Kayero", "Moto du surintendant", "VEH", "Moto", "MOYEN", "NA", None, 1, 2019, 7_500_000, 7, "", "", 0),
    ("BHM", "Cankuzo", "Église paroissiale de Cankuzo", "IMM", "Église", "BON", "TITRE", 700, 1, 2002, 150_000_000, 60, "", "", 0),
    ("BHM", "Cankuzo", "Forage de Cankuzo", "INF", "Forage", "MOYEN", "NA", None, 1, 2017, 32_000_000, 25, "GBGM", "6", 2100),
    ("BHM", "Murore", "Forage de Murore", "INF", "Forage", "MAUVAIS", "NA", None, 1, 2011, 25_000_000, 25, "", "6", 1700),
    ("BHM", "Murore", "Église de Murore", "IMM", "Église", "MAUVAIS", "SANS_TITRE", 450, 1, 1968, 60_000_000, 60, "", "", 0),
    ("BHM", "Murehe", "Centre de santé de Murehe", "IMM", "Centre de santé", "CONSTRUCTION", "TITRE", 900, 1, 2025, 210_000_000, 50, "UMDA", "3", 0),
    ("BHM", "Murehe", "Maison d'hôtes de Murehe", "IMM", "Maison d'hôtes", "CONSTRUCTION", "TITRE", 300, 1, 2025, 80_000_000, 50, "", "", 0),
    ("BHM", "Murehe", "Terrain de Murehe", "FON", "Terrain", "BON", "SANS_TITRE", 25_000, 1, 1975, 15_000_000, None, "", "", 0),
    ("BHM", "Kinyinya", "Porcherie de Kinyinya", "AGR", "Porcherie", "BON", "NA", 400, 60, 2022, 18_000_000, 8, "YAI", "2", 60),
    ("BHM", "Kinyinya", "Champs de manioc de Kinyinya", "AGR", "Champ de manioc", "BON", "NA", 50_000, 1, 2020, 8_000_000, 6, "", "2", 3400),
    ("BHM", "Kinyinya", "Terrain paroissial de Kinyinya", "FON", "Terrain", "BON", "EN_COURS", 12_000, 1, 1990, 8_000_000, None, "", "", 0),
    ("BTN", "Ngozi", "Centre de santé de Ngozi", "IMM", "Centre de santé", "CONSTRUCTION", "TITRE", 950, 1, 2025, 240_000_000, 50, "UMDA", "3", 0),
    ("BTN", "Ngozi", "Église paroissiale de Ngozi", "IMM", "Église", "BON", "TITRE", 800, 1, 2006, 170_000_000, 60, "", "", 0),
    ("BTN", "Ngozi", "Terrain paroissial de Ngozi", "FON", "Terrain", "BON", "TITRE", 18_000, 1, 2001, 25_000_000, None, "", "", 0),
    ("BTN", "Ngozi", "Champignonnière de Ngozi", "AGR", "Champignons comestibles", "BON", "NA", 200, 1, 2024, 9_000_000, 6, "YAI", "2", 25),
    ("BTN", "Ngozi", "Moto du district", "VEH", "Moto", "BON", "NA", None, 1, 2023, 8_500_000, 7, "", "", 0),
    ("BJM", "Rohero", "Église paroissiale de Rohero", "IMM", "Église", "BON", "TITRE", 1500, 1, 1998, 620_000_000, 60, "", "", 0),
    ("BJM", "Rohero", "Terrain paroissial de Rohero", "FON", "Terrain", "BON", "TITRE", 4_000, 1, 1996, 90_000_000, None, "", "", 0),
    ("BJM", "Muyange", "Forage de Muyange", "INF", "Forage", "BON", "NA", None, 1, 2025, 45_000_000, 25, "UMCOR et GBGM", "6", 3500),
    ("BJM", "Muyange", "Église locale de Muyange", "IMM", "Église", "MOYEN", "SANS_TITRE", 400, 1, 2010, 55_000_000, 60, "", "", 0),
    ("BJM", "Buhonga", "Terrain de la station de Buhonga", "FON", "Terrain", "BON", "TITRE", 40_000, 1, 1950, 20_000_000, None, "", "", 0),
    ("BJM", "Buhonga", "Église de Buhonga", "IMM", "Église", "MOYEN", "TITRE", 600, 1, 1972, 95_000_000, 60, "", "", 0),
    ("BJM", "Buhonga", "Forage de Buhonga", "INF", "Forage", "BON", "NA", None, 1, 2019, 35_000_000, 25, "UMCOR", "6", 2400),
    ("BJM", "Rohero", "Pick-up de la paroisse de Rohero", "VEH", "Pick-up", "BON", "NA", None, 1, 2022, 95_000_000, 10, "", "", 0),
]

# district, nom, domaine, statut, avancement, budget, dépense, financeur, ODD, bénéficiaires, début, fin, bien lié
PROJETS = [
    ("BTN", "Construction du centre de santé de Ngozi", "SANTE", "EN_COURS", 65, 240_000_000, 158_000_000, "UMDA", "3", 15_000, 2025, 2027, "Centre de santé de Ngozi"),
    ("BHM", "Centre de santé et maison d'hôtes de Murehe", "SANTE", "EN_COURS", 55, 290_000_000, 162_000_000, "UMDA", "3", 12_000, 2025, 2027, "Centre de santé de Murehe"),
    ("BRG", "Achèvement de l'école d'infirmières de Kayero", "EDUCATION", "EN_COURS", 40, 310_000_000, 118_000_000, "Health Board", "3,4", 300, 2024, 2027, "École d'infirmières de Kayero"),
    ("GIT", "Université théologique et de leadership de Mweya", "EDUCATION", "EN_COURS", 12, 1_200_000_000, 95_000_000, "Conférence", "4", 1_500, 2025, 2030, "Université théologique de Mweya"),
    ("BRG", "Usine de transformation du tournesol (Kumoso)", "AGRICULTURE", "EN_COURS", 30, 420_000_000, 121_000_000, "UMDA", "2,5", 2_000, 2025, 2027, "Usine de transformation du tournesol de Kumoso"),
    ("BJM", "Forage de Muyange", "EAU", "TERMINE", 100, 45_000_000, 44_200_000, "UMCOR et GBGM", "6", 3_500, 2025, 2025, "Forage de Muyange"),
    ("BHM", "Réhabilitation du forage de Murore", "EAU", "PREVU", 0, 18_000_000, 0, "", "6", 1_700, 2026, 2027, "Forage de Murore"),
    ("GIT", "Prévention du paludisme — Imagine No Malaria", "SANTE", "EN_COURS", 70, 60_000_000, 41_000_000, "Imagine No Malaria", "3", 25_000, 2023, 2026, None),
    ("GIT", "Cours de couture du Centre des Femmes", "FEMMES", "EN_COURS", 80, 12_000_000, 9_100_000, "Conférence", "5", 120, 2023, 2026, "Centre des Femmes Méthodistes Unies"),
    ("GIT", "Coopérative Abundant Life", "FEMMES", "EN_COURS", 60, 35_000_000, 20_000_000, "Femmes de la Conférence", "5", 400, 2022, 2027, None),
    ("GIT", "Ministère des sourds et malentendants", "INCLUSION", "EN_COURS", 50, 15_000_000, 7_600_000, "Global Ministries", "10", 580, 2025, 2027, None),
    ("BRG", "Aide humanitaire aux réfugiés congolais de Musenyi", "HUMANITAIRE", "EN_COURS", 45, 75_000_000, 33_000_000, "UMDA", "2,3,10", 1_200, 2025, 2026, "Site d'accueil humanitaire de Musenyi"),
    ("BHM", "Projets agricoles YAI — porcherie et manioc", "AGRICULTURE", "EN_COURS", 75, 28_000_000, 21_000_000, "YAI", "2", 3_400, 2022, 2026, "Porcherie de Kinyinya"),
    ("BJM", "Don d'EPI et de médicaments contre le choléra", "SANTE", "TERMINE", 100, 22_000_000, 22_000_000, "UMDA", "3", 8_000, 2024, 2024, None),
]

# Prix de référence des terrains (BIF/m²) près du chef-lieu, pour les ventes comparables fictives
PRIX_M2 = {"BJM": 45_000, "GIT": 22_000, "BTN": 14_000, "BHM": 6_000, "BRG": 5_000}


class Command(BaseCommand):
    help = "Charge des données de démonstration (lieux réels, chiffres fictifs)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Efface les données existantes avant de charger")

    def handle(self, *args, reset=False, **kwargs):
        random.seed(2026)
        if Bien.objects.exists() and not reset:
            self.stdout.write(self.style.WARNING("Des données existent déjà. Utilisez --reset pour recharger."))
            return
        with transaction.atomic():
            if reset:
                from metier import models as mm
                for m in (mm.Constat, mm.Campagne, mm.Avis, mm.OrdreTravail, mm.Demande, mm.Loyer, mm.Bail, mm.PlanMaintenance,
                          mm.Fournisseur, mm.Echeance, mm.Budget, mm.ClotureExercice):
                    m.objects.all().delete()
                for m in (Declaration, Mesure, Alerte, Capteur, Transaction, Mouvement, Document, Projet, Bien, Paroisse,
                          ComparableMarche, EntrainementModele, JournalAction, Profil):
                    m.objects.all().delete()
                District.objects.all().delete()
                Organisation.objects.all().delete()
                User.objects.filter(username__in=[u[0] for u in self._comptes()] + ["admin.rwanda", "tresorier.rwanda"]).delete()
            self.org = Organisation.objects.create(
                nom="Église Méthodiste Unie du Burundi", sigle="EMU Burundi", slug="emu-burundi", pays="Burundi",
                devise="BIF", taux_usd=2950, langue="fr", whatsapp_numero="+25722000000",
            )
            self.districts = self._districts()
            self._utilisateurs()
            self.biens = self._biens()
            self._projets()
            self._documents()
            self._transactions()
            self._comparables()
            self._iot()
            self._declarations()
            rwanda = self._rwanda()
        self.stdout.write("Entraînement des modèles d'IA (un modèle par organisation)...")
        for org in (rwanda, self.org):
            m = valorisation.entrainer(org.pk)
            valorisation.valoriser_tout(Bien.objects.filter(district__organisation=org).select_related("district"))
            predictions.recalculer_risques(Bien.objects.filter(district__organisation=org))
            a = anomalies.analyser(Transaction.objects.filter(district__organisation=org))
        from metier import demo
        demo.charger(self.org)
        self.stdout.write(self.style.SUCCESS(
            f"Terminé : {Bien.objects.count()} biens, {Projet.objects.count()} projets, "
            f"{Transaction.objects.count()} transactions ({a['anomalies']} anomalies), "
            f"{Mesure.objects.count()} mesures IoT, R² valorisation = {m['r2_validation_croisee']}"
        ))
        self.stdout.write(f"Comptes de démonstration (mot de passe : {MOT_DE_PASSE}) : " + ", ".join(u[0] for u in self._comptes()))
        self.stdout.write("Deuxième organisation de démonstration (en anglais) : admin.rwanda, tresorier.rwanda")

    # ------------------------------------------------------------------
    def _districts(self):
        res = {}
        for code, nom, siege, lat, lon, anciens in DISTRICTS:
            d = District.objects.create(organisation=self.org, code=code, nom=nom, siege=siege, latitude=lat, longitude=lon,
                                        anciens_districts=anciens)
            res[code] = d
            for pnom, plat, plon in PAROISSES[code]:
                Paroisse.objects.create(nom=pnom, district=d, latitude=plat, longitude=plon,
                                        membres=random.randint(800, 6000))
        return res

    def _comptes(self):
        return [
            ("admin", "Administrateur", "Système", Profil.Role.ADMIN, None, ""),
            ("eveque", "Direction", "Épiscopale", Profil.Role.EVEQUE, None, ""),
            ("tresorier", "Trésorier", "Conférence", Profil.Role.TRESORIER, None, ""),
            ("surintendant.gitega", "Surintendant", "Gitega", Profil.Role.SURINTENDANT, "GIT", "+25779000002"),
            ("agent.burunga", "Agent", "Burunga", Profil.Role.AGENT, "BRG", "+25779000001"),
        ]

    def _utilisateurs(self):
        for username, prenom, nom, role, dist, tel in self._comptes():
            u = User.objects.create_user(username, password=MOT_DE_PASSE, first_name=prenom, last_name=nom)
            if role == Profil.Role.ADMIN:
                u.is_staff = u.is_superuser = True
                u.save()
            Profil.objects.create(user=u, organisation=self.org, role=role, district=self.districts.get(dist), telephone=tel)

    def _biens(self):
        res = {}
        for (dc, pnom, nom, cat, st, etat, jur, surf, qte, annee, val, duree, fin, odd, benef) in BIENS:
            d = self.districts[dc]
            p = Paroisse.objects.get(district=d, nom=pnom)
            b = Bien.objects.create(
                nom=nom, categorie=cat, sous_type=st, district=d, paroisse=p, etat=etat, statut_juridique=jur,
                surface_m2=surf, quantite=qte, date_acquisition=date(annee, random.randint(1, 12), random.randint(1, 28)),
                valeur_acquisition=Decimal(val), duree_vie_ans=duree,
                latitude=p.latitude + random.uniform(-0.01, 0.01), longitude=p.longitude + random.uniform(-0.01, 0.01),
                financeur=fin, odd=odd, beneficiaires=benef, responsable=f"Responsable {p.nom}",
                description="Donnée de démonstration : à remplacer par l'inventaire réel.",
            )
            res[nom] = b
            Mouvement.objects.create(bien=b, type="ACQUISITION", date=b.date_acquisition, montant=b.valeur_acquisition,
                                     description="Acquisition / mise en service", auteur="Conférence")
            # Entretiens : récents pour la plupart des biens, absents pour quelques-uns
            if cat not in ("FON",) and etat != "CONSTRUCTION" and random.random() > 0.2:
                for _ in range(random.randint(1, 3)):
                    jours = random.randint(30, 900) if etat != "MAUVAIS" else random.randint(500, 1200)
                    Mouvement.objects.create(
                        bien=b, type=random.choice(["MAINTENANCE", "INSPECTION", "REPARATION"]),
                        date=date.today() - timedelta(days=jours),
                        montant=Decimal(round(float(val) * random.uniform(0.005, 0.03), -3)),
                        description="Entretien courant (démo)", auteur=f"Responsable {p.nom}",
                    )
        return res

    def _projets(self):
        for (dc, nom, dom, statut, av, budget, dep, fin, odd, benef, d1, d2, bien) in PROJETS:
            b = self.biens.get(bien) if bien else None
            d = self.districts[dc]
            Projet.objects.create(
                nom=nom, domaine=dom, district=d, bien=b, statut=statut, avancement=av, budget=Decimal(budget),
                depense=Decimal(dep), financeur=fin, odd=odd, beneficiaires=benef, date_debut=date(d1, 3, 1),
                date_fin_prevue=date(d2, 12, 31), latitude=b.latitude if b else d.latitude + random.uniform(-0.03, 0.03),
                longitude=b.longitude if b else d.longitude + random.uniform(-0.03, 0.03),
                description="Projet cité dans le rapport de l'Église ; budget et avancement fictifs (démo).",
            )

    def _documents(self):
        chemin = Path(settings.BASE_DIR) / "donnees" / "rapport_emu_burundi.txt"
        if chemin.exists():
            Document.objects.create(organisation=self.org, titre="Rapport historique et institutionnel de l'EMU Burundi", type="RAPPORT",
                                    contenu=chemin.read_text(encoding="utf-8"), date=date(2025, 10, 20))
        b = self.biens
        docs = [
            ("Titre foncier — Terrain de la station missionnaire de Kayero (démo)", "TITRE_FONCIER", b["Terrain de la station missionnaire de Kayero"],
             "Certificat d'enregistrement du terrain de la station missionnaire de Kayero, province de Rutana, ouverte en 1938. "
             "Propriétaire : Église Méthodiste Unie du Burundi. Superficie : 8,5 hectares. Le terrain comprend l'église historique, "
             "le forage et les champs de tournesol cultivés par les femmes du district. Document de démonstration.", date(2003, 5, 14)),
            ("Convention de financement UMCOR / GBGM — Forage de Muyange (démo)", "CONVENTION", b["Forage de Muyange"],
             "Convention entre UMCOR, GBGM et l'Église Méthodiste Unie du Burundi pour le forage de l'église locale de Muyange, "
             "district de Bujumbura. Le forage a été inauguré en juin 2025. L'Église s'engage à assurer l'entretien de la pompe, "
             "à suivre le niveau d'eau et à rendre compte du nombre de personnes desservies, estimé à 3 500. Document de démonstration.", date(2025, 2, 10)),
            ("Rapport d'inspection — Église et forage de Murore (démo)", "RAPPORT", b["Église de Murore"],
             "Inspection du site de Murore, district de Buhumuza. La toiture de l'église présente des infiltrations et des fissures "
             "sur le mur est. Le forage de Murore montre une baisse du niveau d'eau et la pompe doit être réhabilitée. "
             "Le terrain de Murore n'a pas de titre de propriété : régularisation recommandée en priorité. Document de démonstration.", date(2026, 6, 3)),
            ("Contrat de construction — Centre de santé de Ngozi (démo)", "CONTRAT", b["Centre de santé de Ngozi"],
             "Contrat de construction du centre de santé de Ngozi, district de Butanyerera, financé par l'UMDA. Délai d'exécution : "
             "24 mois. Paiement par tranches selon l'avancement constaté. Le centre contribue à l'objectif du Health Board : "
             "un centre de santé par district d'ici 2030. Document de démonstration.", date(2025, 4, 22)),
            ("Procès-verbal du comité exécutif du 10 mai 2025 (synthèse)", "RAPPORT", None,
             "Réunion du comité exécutif à la Cathédrale Saint-Pierre de Gitega, présidée par l'évêque. 53 membres présents. "
             "Décisions : feu vert à la régionalisation du Burundi ; audits réguliers de toutes les institutions financières ; "
             "création d'un département de collecte de fonds pour les étudiants de l'Africa University ; élargissement des projets "
             "selon les besoins de l'Église et de la communauté.", date(2025, 5, 10)),
        ]
        for titre, typ, bien, contenu, dt in docs:
            Document.objects.create(organisation=self.org, titre=titre, type=typ, bien=bien, district=bien.district if bien else None,
                                    contenu=contenu, date=dt)

    def _transactions(self):
        debut = date(2024, 10, 1)
        poids = {"GIT": 1.6, "BJM": 1.8, "BRG": 1.0, "BHM": 0.9, "BTN": 0.8}
        projets = list(Projet.objects.all())
        lignes = []
        for i in range(24):
            mois = date(debut.year + (debut.month - 1 + i) // 12, (debut.month - 1 + i) % 12 + 1, 1)
            saison = 1.35 if mois.month in (8, 12) else 1.0  # conférence annuelle et Noël
            croissance = 1 + 0.012 * i
            for code, d in self.districts.items():
                w = poids[code]

                def ajout(sens, cat, montant, canal="BANQUE", tiers="", desc="", projet=None, jour=None, devise="BIF"):
                    jour = jour or random.randint(1, 28)
                    lignes.append(Transaction(date=mois.replace(day=jour), sens=sens, categorie=cat, montant=Decimal(round(montant, -2) if devise == "BIF" else round(montant, 2)),
                                              devise=devise, canal=canal, district=d, tiers=tiers, description=desc, projet=projet))

                for semaine in range(4):
                    ajout("RECETTE", "DIME", 3_200_000 * w * saison * croissance * random.uniform(0.8, 1.2),
                          canal=random.choice(["BANQUE", "MOBILE", "ESPECES"]), tiers="Fidèles", desc="Dîmes et offrandes",
                          jour=min(28, 2 + 7 * semaine))
                ajout("DEPENSE", "SALAIRE", 6_500_000 * w * croissance * random.uniform(0.97, 1.03), tiers="Pasteurs et personnel", desc="Salaires du mois", jour=25)
                for _ in range(random.randint(2, 4)):
                    ajout("DEPENSE", "FONCTIONNEMENT", random.uniform(150_000, 900_000) * w,
                          canal=random.choice(["BANQUE", "ESPECES", "MOBILE"]), tiers=random.choice(["Papeterie Centrale", "Regideso", "Station Interpetrol", "Onatel"]),
                          desc="Frais de fonctionnement", jour=random.choice([2, 5, 8, 12, 15, 19, 22, 26]))
                if random.random() < 0.5:
                    ajout("DEPENSE", "MAINTENANCE", random.uniform(300_000, 2_500_000), tiers=random.choice(["Atelier Ndikumana", "Plomberie du Centre", "Garage Moderne"]),
                          desc="Entretien de biens")
                if random.random() < 0.3:
                    ajout("RECETTE", "REVENU_PROJET", random.uniform(500_000, 3_000_000) * w, canal="MOBILE",
                          tiers="Coopératives et projets YAI", desc="Ventes (tournesol, porcs, champignons, couture)")
                if random.random() < 0.15:
                    ajout("RECETTE", "DON", random.uniform(500, 4000), devise="USD", tiers="Conférence d'Allemagne du Sud-Ouest", desc="Don « Unis dans la Prière »")
            # Subventions et construction, au niveau des projets
            for p in projets:
                if p.statut in ("EN_COURS", "TERMINE") and p.date_debut <= mois <= p.date_fin_prevue and random.random() < 0.35:
                    tranche = float(p.budget) / 18 * random.uniform(0.7, 1.3)
                    lignes.append(Transaction(date=mois.replace(day=random.randint(3, 27)), sens="DEPENSE",
                                              categorie="CONSTRUCTION" if p.domaine in ("SANTE", "EDUCATION", "EAU", "AGRICULTURE") else "ACHAT",
                                              montant=Decimal(round(tranche, -3)), district=p.district, projet=p,
                                              tiers="Entreprise de construction" if p.domaine != "FEMMES" else "Fournisseur", description=f"Tranche — {p.nom}"))
                    if random.random() < 0.5 and p.financeur:
                        lignes.append(Transaction(date=mois.replace(day=random.randint(1, 10)), sens="RECETTE", categorie="SUBVENTION",
                                                  montant=Decimal(round(tranche * 1.05, -3)), district=p.district, projet=p,
                                                  tiers=p.financeur, description=f"Subvention — {p.nom}"))
        # Anomalies volontairement injectées pour la démonstration
        g, b = self.districts["GIT"], self.districts["BHM"]
        lignes += [
            Transaction(date=date(2026, 3, 9), sens="DEPENSE", categorie="FONCTIONNEMENT", montant=Decimal(14_500_000), canal="ESPECES",
                        district=b, tiers="Fournisseur non identifié", description="Achat divers"),
            Transaction(date=date(2026, 5, 12), sens="DEPENSE", categorie="MAINTENANCE", montant=Decimal(3_750_000), district=g,
                        tiers="Garage Moderne", description="Réparation véhicule"),
            Transaction(date=date(2026, 5, 13), sens="DEPENSE", categorie="MAINTENANCE", montant=Decimal(3_750_000), district=g,
                        tiers="Garage Moderne", description="Réparation véhicule"),
            Transaction(date=date(2026, 7, 5), sens="DEPENSE", categorie="ACHAT", montant=Decimal(9_800_000), canal="ESPECES",
                        district=self.districts["BRG"], tiers="Particulier", description="Achat de matériel"),
            Transaction(date=date(2026, 8, 30), sens="DEPENSE", categorie="SALAIRE", montant=Decimal(38_000_000),
                        district=self.districts["BTN"], tiers="Pasteurs et personnel", description="Salaires du mois"),
        ]
        for t in lignes:
            t.save()

    def _comparables(self):
        """Ventes de référence FICTIVES pour entraîner le modèle de valorisation."""
        for code, d in self.districts.items():
            for _ in range(36):
                cat = random.choice(["FON", "FON", "IMM"])
                dist = random.uniform(0.2, 40)
                if cat == "FON":
                    surf = math.exp(random.uniform(math.log(300), math.log(150_000)))
                    prix = PRIX_M2[code] * math.exp(-0.045 * dist) * surf ** 0.93
                    age, etat = 0, "BON"
                else:
                    surf = math.exp(random.uniform(math.log(80), math.log(3000)))
                    age = random.uniform(0, 60)
                    etat = random.choice(["BON", "BON", "MOYEN", "MAUVAIS"])
                    f_etat = {"BON": 1.0, "MOYEN": 0.8, "MAUVAIS": 0.55}[etat]
                    prix = surf * (300_000 * f_etat * max(0.3, 1 - age / 80) + 0.6 * PRIX_M2[code] * math.exp(-0.045 * dist) * 4)
                prix *= math.exp(random.gauss(0, 0.18))
                ComparableMarche.objects.create(
                    categorie=cat, district=d, surface_m2=round(surf), age_ans=round(age, 1), etat=etat,
                    distance_ville_km=round(dist, 1), prix_bif=Decimal(round(prix, -3)),
                    date=date(2025, 1, 1) + timedelta(days=random.randint(0, 600)), source="Démonstration (fictif)",
                )

    def _iot(self):
        b = self.biens
        capteurs = [
            ("FOR-MUY-NIV", "NIVEAU_EAU", "Forage de Muyange", "m", 2.0, None, 6.5),
            ("FOR-MUY-DEB", "DEBIT", "Forage de Muyange", "L/min", 10, None, 32),
            ("FOR-KAY-NIV", "NIVEAU_EAU", "Forage de Kayero", "m", 2.0, None, 5.8),
            ("FOR-CAN-NIV", "NIVEAU_EAU", "Forage de Cankuzo", "m", 2.0, None, 4.9),
            ("FOR-MUR-NIV", "NIVEAU_EAU", "Forage de Murore", "m", 2.0, None, 3.6),
            ("FOR-BUH-DEB", "DEBIT", "Forage de Buhonga", "L/min", 10, None, 28),
            ("CS-GAH-FRIGO", "TEMPERATURE", "Centre de santé de Gahambwe", "°C", 2, 8, 5.0),
            ("CATH-GIT-NRJ", "ENERGIE", "Cathédrale Saint-Pierre de Gitega", "kWh", None, 45, 18),
        ]
        maintenant = timezone.now().replace(minute=0, second=0, microsecond=0)
        heures = 7 * 24
        for code, typ, bien, unite, smin, smax, base in capteurs:
            c = Capteur.objects.create(code=code, type=typ, bien=b[bien], unite=unite, seuil_min=smin, seuil_max=smax)
            mesures = []
            for h in range(heures):
                t = maintenant - timedelta(hours=heures - 1 - h)
                cycle = math.sin(2 * math.pi * (t.hour - 6) / 24)
                if typ == "NIVEAU_EAU":
                    v = base - 0.6 * max(0, cycle) + random.gauss(0, 0.08)
                    if code == "FOR-MUR-NIV":  # baisse progressive : panne de pompe / nappe qui baisse
                        v = base - 1.9 * h / heures - 0.5 * max(0, cycle) + random.gauss(0, 0.05)
                elif typ == "DEBIT":
                    v = max(0, base * (0.6 + 0.4 * max(0, cycle)) + random.gauss(0, 1.5))
                elif typ == "TEMPERATURE":
                    v = base + 0.6 * cycle + random.gauss(0, 0.2)
                    if h > heures - 6:  # coupure de courant : le réfrigérateur se réchauffe
                        v = base + 1.2 * (h - (heures - 6)) + random.gauss(0, 0.2)
                else:
                    v = max(0, base * (0.4 + 0.8 * max(0, cycle)) + random.gauss(0, 1.5))
                mesures.append(Mesure(capteur=c, horodatage=t, valeur=round(v, 2)))
            Mesure.objects.bulk_create(mesures)
            c.derniere_valeur, c.derniere_mesure = mesures[-1].valeur, mesures[-1].horodatage
            c.save()
            verifier_seuils(c, c.derniere_valeur)

    def _declarations(self):
        """Quelques messages WhatsApp reçus des agents, en attente de validation."""
        from patrimoine.whatsapp import traiter_message

        for tel, texte in [
            ("+25779000001", "Nouveau forage à Gahambwe, en bon état, financé par UMCOR, 38 000 000 BIF"),
            ("+25779000001", "7 chèvres données aux femmes de Kayero, bon état"),
            ("+25779000002", "Le toit de l'école de Nyabugogo fuit, mauvais état"),
        ]:
            traiter_message(tel, texte)

    def _rwanda(self):
        """Deuxième organisation de démonstration (interface en anglais, monnaie RWF) : tout est fictif."""
        org = Organisation.objects.create(
            nom="Église Méthodiste Unie du Rwanda (démonstration)", sigle="EMU Rwanda", slug="emu-rwanda", pays="Rwanda",
            devise="RWF", taux_usd=1450, langue="en",
        )
        prix_m2 = {"KGL": 60_000, "HUY": 18_000, "MUS": 22_000}
        districts = {}
        for code, nom, lat, lon in [("KGL", "Kigali", -1.9441, 30.0619), ("HUY", "Huye", -2.5967, 29.7394), ("MUS", "Musanze", -1.4996, 29.6347)]:
            d = District.objects.create(organisation=org, code=code, nom=nom, siege=nom, latitude=lat, longitude=lon)
            Paroisse.objects.create(nom=nom, district=d, latitude=lat, longitude=lon, membres=random.randint(900, 4000))
            districts[code] = d
            for _ in range(30):
                cat = random.choice(["FON", "FON", "IMM"])
                dist = random.uniform(0.2, 30)
                surf = math.exp(random.uniform(math.log(200), math.log(60_000))) if cat == "FON" else math.exp(random.uniform(math.log(80), math.log(2000)))
                prix = prix_m2[code] * math.exp(-0.04 * dist) * surf ** 0.93 if cat == "FON" else surf * 250_000
                ComparableMarche.objects.create(categorie=cat, district=d, surface_m2=round(surf), distance_ville_km=round(dist, 1),
                                                prix_bif=Decimal(round(prix * math.exp(random.gauss(0, 0.15)), -3)),
                                                date=date(2025, 6, 1), source="Démonstration (fictif)")
        for code, nom, cat, st, etat, jur, surf, annee, val, odd, benef in [
            ("KGL", "Église de Kigali", "IMM", "Église", "BON", "TITRE", 900, 2004, 380_000_000, "", 0),
            ("KGL", "Terrain de Kigali", "FON", "Terrain", "BON", "TITRE", 3000, 2001, 90_000_000, "", 0),
            ("HUY", "École primaire de Huye", "IMM", "École", "MOYEN", "TITRE", 1100, 2010, 260_000_000, "4", 520),
            ("HUY", "Forage de Huye", "INF", "Forage", "BON", "NA", None, 2022, 21_000_000, "6", 1800),
            ("MUS", "Centre de santé de Musanze", "IMM", "Centre de santé", "BON", "TITRE", 700, 2016, 210_000_000, "3", 7000),
            ("MUS", "Terrain de Musanze", "FON", "Terrain", "BON", "SANS_TITRE", 12_000, 1995, 15_000_000, "", 0),
        ]:
            d = districts[code]
            Bien.objects.create(nom=nom, categorie=cat, sous_type=st, district=d, paroisse=d.paroisses.first(), etat=etat,
                                statut_juridique=jur, surface_m2=surf, date_acquisition=date(annee, 6, 1), valeur_acquisition=Decimal(val),
                                latitude=d.latitude + random.uniform(-0.01, 0.01), longitude=d.longitude + random.uniform(-0.01, 0.01),
                                odd=odd, beneficiaires=benef, description="Donnée de démonstration (fictive).")
        Projet.objects.create(nom="Extension of Huye primary school", domaine="EDUCATION", district=districts["HUY"], statut="EN_COURS",
                              avancement=35, budget=Decimal(120_000_000), depense=Decimal(40_000_000), odd="4", beneficiaires=300,
                              date_debut=date(2026, 1, 1), date_fin_prevue=date(2027, 6, 30),
                              latitude=districts["HUY"].latitude, longitude=districts["HUY"].longitude)
        for i in range(12):
            mois = date(2025 + (9 + i) // 12, (9 + i) % 12 + 1, 1)
            for code, d in districts.items():
                for _ in range(3):
                    Transaction(date=mois.replace(day=random.randint(1, 28)), sens="RECETTE", categorie="DIME", devise="RWF",
                                montant=Decimal(round(random.uniform(800_000, 1_600_000), -2)), district=d, tiers="Members").save()
                Transaction(date=mois.replace(day=25), sens="DEPENSE", categorie="SALAIRE", devise="RWF",
                            montant=Decimal(round(random.uniform(1_800_000, 2_200_000), -2)), district=d, tiers="Staff").save()
        for username, prenom, role in [("admin.rwanda", "Administrator", Profil.Role.ADMIN), ("tresorier.rwanda", "Treasurer", Profil.Role.TRESORIER)]:
            u = User.objects.create_user(username, password=MOT_DE_PASSE, first_name=prenom, last_name="Rwanda")
            Profil.objects.create(user=u, organisation=org, role=role)
        return org
