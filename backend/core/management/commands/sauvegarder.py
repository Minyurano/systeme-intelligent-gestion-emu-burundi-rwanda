"""
Sauvegarde complète : base de données (format JSON portable) et fichiers (photos, documents).

    python manage.py sauvegarder                 # crée sauvegardes/umurage_AAAAMMJJ_HHMM.zip
    python manage.py sauvegarder --garder 30     # conserve les 30 dernières

À planifier chaque nuit (Planificateur de tâches Windows, cron, ou service Docker).
Restauration : décompresser l'archive, puis
    python manage.py migrate && python manage.py loaddata donnees.json
et recopier le dossier media/.
"""
import io
import zipfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sauvegarde la base de données et les fichiers dans une archive zip datée."

    def add_arguments(self, parser):
        parser.add_argument("--garder", type=int, default=14, help="Nombre de sauvegardes à conserver")
        parser.add_argument("--dossier", default=None, help="Dossier de destination")

    def handle(self, garder, dossier, **kw):
        dest = Path(dossier) if dossier else settings.SAUVEGARDES_DIR
        dest.mkdir(parents=True, exist_ok=True)
        nom = dest / f"umurage_{datetime.now():%Y%m%d_%H%M%S}.zip"

        donnees = io.StringIO()
        call_command("dumpdata", exclude=["contenttypes", "auth.permission", "sessions", "admin.logentry"],
                     natural_foreign=True, indent=1, stdout=donnees)
        media = Path(settings.MEDIA_ROOT)
        nb = 0
        with zipfile.ZipFile(nom, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("donnees.json", donnees.getvalue())
            if media.exists():
                for f in media.rglob("*"):
                    if f.is_file():
                        z.write(f, Path("media") / f.relative_to(media))
                        nb += 1
            z.writestr("LISEZMOI.txt", __doc__)

        anciennes = sorted(dest.glob("umurage_*.zip"))[:-garder] if garder > 0 else []
        for a in anciennes:
            a.unlink()
        taille = nom.stat().st_size / 1e6
        self.stdout.write(self.style.SUCCESS(f"Sauvegarde créée : {nom} ({taille:.1f} Mo, {nb} fichiers). {len(anciennes)} ancienne(s) supprimée(s)."))
