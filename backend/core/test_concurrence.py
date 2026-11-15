"""
Écritures simultanées : chaîne du journal d'audit et numéros de membre.

Ces tests demandent une vraie base PostgreSQL (SQLite sérialise déjà toutes les écritures) :
  POSTGRES_DB=umurage POSTGRES_HOST=... python manage.py test core.test_concurrence
Sous SQLite, ils sont ignorés.
"""
import threading
from unittest import skipUnless

from django.db import connection, connections
from django.test import TransactionTestCase

from core.models import District, JournalAction, Organisation, Paroisse

FILS, PAR_FIL = 12, 6


def en_parallele(travail):
    """Lance `travail(i)` dans FILS fils qui démarrent au même instant ; renvoie les erreurs."""
    depart, erreurs = threading.Barrier(FILS), []

    def fil(i):
        try:
            depart.wait()
            for j in range(PAR_FIL):
                travail(i, j)
        except Exception as e:  # noqa: BLE001 - on veut toutes les erreurs
            erreurs.append(repr(e))
        finally:
            connections.close_all()

    fils = [threading.Thread(target=fil, args=(i,)) for i in range(FILS)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    return erreurs


@skipUnless(connection.vendor == "postgresql", "nécessite PostgreSQL")
class EcrituresSimultaneesTests(TransactionTestCase):
    def setUp(self):
        org = Organisation.objects.create(nom="Église test", sigle="ET", slug="eglise-test", pays="Burundi")
        self.district = District.objects.create(organisation=org, code="TST", nom="Test", siege="Test")
        self.paroisse = Paroisse.objects.create(nom="Paroisse test", district=self.district)
        self.org = org

    def test_chaine_du_journal_reste_intacte(self):
        def ecrire(i, j):
            JournalAction.objects.create(organisation=self.org, action="CREATION", objet_type="Test",
                                         objet_id=f"{i}-{j}", objet_libelle=f"écriture {i}-{j}")

        self.assertEqual(en_parallele(ecrire), [])
        self.assertEqual(JournalAction.objects.count(), FILS * PAR_FIL)
        intact, n = JournalAction.verifier_chaine()
        self.assertTrue(intact, f"chaîne cassée à l'entrée {n}")
        # Chaque maillon a un précédent différent : aucun « embranchement »
        precedentes = list(JournalAction.objects.values_list("empreinte_precedente", flat=True))
        self.assertEqual(len(precedentes), len(set(precedentes)))

    def test_numeros_de_membre_uniques_et_continus(self):
        from metier.models import MembreEglise

        def enregistrer(i, j):
            MembreEglise.objects.create(paroisse=self.paroisse, nom=f"NOM{i}", prenom=f"Prenom{j}", sexe="F")

        self.assertEqual(en_parallele(enregistrer), [])
        rangs = sorted(int(n.rsplit("-", 1)[1]) for n in MembreEglise.objects.values_list("numero", flat=True))
        self.assertEqual(rangs, list(range(1, FILS * PAR_FIL + 1)))
