"""
Restauration d'une sauvegarde créée par `python manage.py sauvegarder`.

    python manage.py restaurer sauvegardes/umurage_20261009_060000.zip --oui

ATTENTION : la base actuelle est entièrement remplacée par le contenu de l'archive.
Testez la restauration chaque trimestre sur une machine de test : une sauvegarde jamais restaurée n'est pas une sauvegarde.
"""
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Remplace la base et les fichiers par le contenu d'une sauvegarde."

    def add_arguments(self, parser):
        parser.add_argument("archive")
        parser.add_argument("--oui", action="store_true", help="Confirme le remplacement des données actuelles")

    def handle(self, archive, oui, **kw):
        chemin = Path(archive)
        if not chemin.exists():
            raise CommandError(f"Archive introuvable : {chemin}")
        if not oui:
            raise CommandError("Ajoutez --oui pour confirmer : toutes les données actuelles seront remplacées.")
        with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(chemin) as z:
            if "donnees.json" not in z.namelist():
                raise CommandError("Archive invalide : donnees.json absent.")
            z.extractall(tmp)
            call_command("migrate", verbosity=0)
            from django.db import connection
            if connection.vendor == "postgresql" and connection.in_atomic_block:
                # Dans une transaction, PostgreSQL refuse TRUNCATE tant que des contrôles de clés étrangères
                # sont en attente : on les exécute d'abord.
                with connection.cursor() as c:
                    c.execute("SET CONSTRAINTS ALL IMMEDIATE")
            call_command("flush", interactive=False, verbosity=0)
            call_command("loaddata", str(Path(tmp) / "donnees.json"), verbosity=0)
            media_src = Path(tmp) / "media"
            nb = 0
            if media_src.exists():
                for f in media_src.rglob("*"):
                    if f.is_file():
                        dest = Path(settings.MEDIA_ROOT) / f.relative_to(media_src)
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, dest)
                        nb += 1
        cache.clear()
        self.stdout.write(self.style.SUCCESS(f"Restauration terminée depuis {chemin.name} ({nb} fichiers)."))
