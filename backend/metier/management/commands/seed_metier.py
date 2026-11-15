from django.core.management.base import BaseCommand

from core.models import Organisation
from metier import demo
from metier.models import Demande


class Command(BaseCommand):
    help = "Charge les données de démonstration des modules métier (approbations, échéances, baux, maintenance, budget, inventaire)."

    def handle(self, *args, **kw):
        org = Organisation.objects.filter(slug="emu-burundi").first()
        if org is None:
            self.stdout.write(self.style.WARNING("Lancez d'abord : python manage.py seed_demo"))
            return
        from django.contrib.auth.models import User
        if not User.objects.filter(username="eveque").exists():
            self.stdout.write(self.style.WARNING("Installation sans comptes de démonstration : rien n'est chargé (protection des données réelles)."))
            return
        if Demande.objects.filter(organisation=org).exists():
            # Installations déjà démarrées : on ajoute seulement le registre des membres s'il est vide
            from metier.models import MembreEglise
            n = MembreEglise.objects.filter(paroisse__district__organisation=org, notes__startswith="Fiche de démonstration").count()
            demo.charger_acces_membres(org)
            demo.charger_contributions(org)
            if n < 160:
                demo.charger_membres(org, User.objects.filter(username="surintendant.gitega").first(), nombre=160 - n, graine=11 + n)
                self.stdout.write(self.style.SUCCESS("Registre des membres de démonstration complété."))
            else:
                self.stdout.write("Les données métier de démonstration sont déjà chargées.")
            return
        demo.charger(org)
        self.stdout.write(self.style.SUCCESS("Données métier de démonstration chargées."))
