"""Contrôles au démarrage (python manage.py check --deploy, et chaque lancement du serveur)."""
from django.conf import settings
from django.core.checks import Warning, register


@register()
def proxy_configure(app_configs, **kwargs):
    if settings.DEBUG or getattr(settings, "NUM_PROXIES_DEFINI", True):
        return []
    return [Warning(
        "UMURAGE_NUM_PROXIES n'est pas défini.",
        hint="Derrière un proxy HTTPS (Caddy, Nginx, Traefik), mettez UMURAGE_NUM_PROXIES=1 : sinon tous les visiteurs "
             "partagent l'adresse du proxy et les limites de tentatives bloquent tout le monde à la fois. Sans proxy, "
             "mettez 0. Vérifiez ensuite avec GET /api/diagnostic/adresse-ip/ (administrateur).",
        id="umurage.W001",
    )]
