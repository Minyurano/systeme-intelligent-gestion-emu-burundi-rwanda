from django.apps import AppConfig


class PatrimoineConfig(AppConfig):
    name = "patrimoine"

    def ready(self):
        from .cache_donnees import brancher_signaux

        brancher_signaux()
