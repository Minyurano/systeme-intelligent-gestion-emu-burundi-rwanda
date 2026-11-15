from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "core"

    def ready(self):
        from . import checks  # noqa: F401 - enregistre les contrôles de démarrage
        from .fichiers import installer

        installer()  # liens signés et temporaires pour tous les fichiers renvoyés par l'API
