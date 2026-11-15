"""
Tâches quotidiennes : loyers du mois, échéances automatiques, entretiens préventifs, inspections des biens à risque, rappels.

Windows (Planificateur de tâches, chaque jour à 6 h) :
    schtasks /Create /SC DAILY /ST 06:00 /TN "UMURAGE taches" /TR "C:\\chemin\\umurage\\backend\\.venv\\Scripts\\python.exe C:\\chemin\\umurage\\backend\\manage.py executer_taches"
Linux (cron) :
    0 6 * * * cd /srv/umurage/backend && .venv/bin/python manage.py executer_taches
Docker : le service « taches » de docker-compose.prod.yml s'en charge.
"""
from django.core.management.base import BaseCommand

from metier.taches import executer_tout


class Command(BaseCommand):
    help = "Exécute les tâches automatiques quotidiennes d'UMURAGE."

    def handle(self, *args, **kw):
        bilan = executer_tout()
        self.stdout.write(self.style.SUCCESS("Tâches exécutées : " + ", ".join(f"{k} = {v}" for k, v in bilan.items())))
