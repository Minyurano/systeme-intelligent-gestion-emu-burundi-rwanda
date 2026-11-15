"""
UMURAGE — Plateforme intelligente de gestion du patrimoine
Église Méthodiste Unie du Burundi

Paramètres Django. Les valeurs sensibles se lisent dans les variables
d'environnement (voir .env.example).
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(key, default=None):
    return os.environ.get(key, default)


SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-umurage-a-changer-en-production-2026")
DEBUG = env("DJANGO_DEBUG", "1") == "1"
# Mode démonstration : affiche les comptes de test sur la page de connexion. Désactivé par défaut en production.
UMURAGE_DEMO = env("UMURAGE_DEMO", "1" if DEBUG else "0") == "1"
# En développement, tout hôte est accepté (essais depuis un téléphone du réseau local).
# En production, la liste doit être donnée explicitement (vérifié plus bas).
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "*" if DEBUG else "").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Tiers
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",  # révocation des jetons (rotation, déconnexion, suspension)
    "django_filters",
    "corsheaders",
    # Applications UMURAGE
    "core",
    "patrimoine",
    "finances",
    "iot",
    "ia",
    "metier",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Base de données -------------------------------------------------------
# SQLite par défaut (démo). Pour la production, définir POSTGRES_DB.
if env("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER", "umurage"),
            "PASSWORD": env("POSTGRES_PASSWORD", ""),
            "HOST": env("POSTGRES_HOST", "localhost"),
            "PORT": env("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": env("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Bujumbura"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- API REST ----------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["core.securite.EstPersonnel"],  # les fidèles (rôle MEMBRE) sont refusés par défaut
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    # Limites anti-abus : tentatives de connexion et appels anonymes
    "DEFAULT_THROTTLE_RATES": {"connexion": "10/min", "anon": "120/min", "rafraichir": "30/min", "mdp_oublie": "5/hour", "mdp_code": "20/hour"},
}

# --- Adresse IP réelle du visiteur (limites de tentatives) -----------------------------------
# Nombre de proxys DE CONFIANCE placés devant Django (Caddy, Nginx, Traefik, répartiteur de charge…).
#   0 (défaut) : l'en-tête X-Forwarded-For est ignoré, on utilise l'adresse de la connexion.
#   1 : un proxy ajoute l'adresse du visiteur à X-Forwarded-For ; on prend la dernière adresse ajoutée.
#   N : N proxys en chaîne.
# Sans ce réglage, Django REST Framework utilisait tout l'en-tête tel qu'envoyé par le client : un attaquant
# changeait d'« adresse » à chaque requête et contournait toutes les limites (connexion, code oublié…).
# Avec un proxy, Django ne doit être joignable QUE par lui (port lié à 127.0.0.1, voir docker-compose.prod.yml).
_proxys = env("UMURAGE_NUM_PROXIES", "")
NUM_PROXIES = int(_proxys) if _proxys.strip().isdigit() else 0
NUM_PROXIES_DEFINI = bool(_proxys.strip())
REST_FRAMEWORK["NUM_PROXIES"] = NUM_PROXIES

# Messagerie (codes « mot de passe oublié ») : la console en développement, SMTP en production
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend" if DEBUG
                    else "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env("EMAIL_USE_TLS", "1") == "1"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "UMURAGE <no-reply@umurage.local>")

SIMPLE_JWT = {
    # Jeton d'accès court, gardé en mémoire par l'application ; rafraîchissement dans un cookie HttpOnly (core/jetons.py)
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = [o for o in env("CORS_ORIGINS", "").split(",") if o]

# --- UMURAGE -----------------------------------------------------------------
UMURAGE = {
    # Taux de change de référence BIF par USD (à mettre à jour ou brancher sur une API)
    "TAUX_USD_BIF": float(env("TAUX_USD_BIF", "2950")),
    # URL publique du frontend (utilisée dans les QR codes)
    "FRONTEND_URL": env("FRONTEND_URL", "http://localhost:5173"),
    # Clé partagée par les capteurs IoT (ESP32) pour envoyer leurs mesures
    "IOT_API_KEY": env("IOT_API_KEY", "umurage-iot-demo-key"),
    # LLM optionnel (API compatible OpenAI : Ollama, vLLM, OpenAI...)
    "LLM_BASE_URL": env("LLM_BASE_URL", ""),   # ex. http://localhost:11434/v1
    "LLM_MODEL": env("LLM_MODEL", "llama3.1"),
    "LLM_API_KEY": env("LLM_API_KEY", "ollama"),
}

# --- Interface web servie par Django (un seul serveur en production) ------------
# Après « npm run build », le dossier frontend/dist est servi à la racine du site.
FRONTEND_DIST = Path(env("FRONTEND_DIST", str(BASE_DIR.parent / "frontend" / "dist")))
if FRONTEND_DIST.exists():
    WHITENOISE_ROOT = FRONTEND_DIST
WHITENOISE_MIMETYPES = {".webmanifest": "application/manifest+json"}

# Cache partagé entre les processus du serveur (indispensable pour limiter les tentatives de connexion)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": env("CACHE_DIR", str(BASE_DIR / ".cache")),
    }
}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024
SAUVEGARDES_DIR = Path(env("SAUVEGARDES_DIR", str(BASE_DIR / "sauvegardes")))
# Durée de validité des liens signés vers les fichiers téléversés (core/fichiers.py)
FICHIERS_LIEN_MINUTES = int(env("FICHIERS_LIEN_MINUTES", "240"))

# --- Sécurité en production -------------------------------------------------------
CSRF_TRUSTED_ORIGINS = [o for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env("DJANGO_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(env("DJANGO_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
    # Inscription à la liste « preload » des navigateurs : décision définitive, à prendre en connaissance de cause
    SECURE_HSTS_PRELOAD = env("DJANGO_HSTS_PRELOAD", "0") == "1"
    if not SECURE_HSTS_PRELOAD:
        SILENCED_SYSTEM_CHECKS = ["security.W021"]
    # La page de supervision reste joignable en HTTP depuis le conteneur lui-même (contrôle de santé Docker)
    SECURE_REDIRECT_EXEMPT = [r"^api/sante/$"]
    if SECRET_KEY.startswith("dev-insecure") or len(SECRET_KEY) < 32:
        raise RuntimeError("Définissez DJANGO_SECRET_KEY (au moins 32 caractères aléatoires) avant de lancer UMURAGE en production.")
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise RuntimeError("Définissez DJANGO_ALLOWED_HOSTS (par exemple umurage.emu-burundi.org, jamais *) avant de lancer UMURAGE en production.")

# --- Journal technique et suivi des erreurs ---------------------------------------
# Les erreurs du serveur (500) et les alertes de sécurité sont toujours écrites avec leur date. LOG_FICHIER ajoute
# un fichier tournant (5 × 5 Mo). Avec SENTRY_DSN, chaque erreur est aussi envoyée à Sentry, ou à GlitchTip
# (logiciel libre compatible, hébergeable par l'Église), sans aucune donnée personnelle.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name} : {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "loggers": {
        "umurage": {"handlers": ["console"], "level": env("LOG_NIVEAU", "INFO")},
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
if env("LOG_FICHIER"):
    LOGGING["handlers"]["fichier"] = {
        "class": "logging.handlers.RotatingFileHandler", "filename": env("LOG_FICHIER"),
        "maxBytes": 5 * 1024 * 1024, "backupCount": 5, "formatter": "simple", "encoding": "utf-8",
    }
    for _nom in LOGGING["loggers"]:
        LOGGING["loggers"][_nom]["handlers"].append("fichier")

if env("SENTRY_DSN"):
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        from config.version import VERSION

        sentry_sdk.init(
            dsn=env("SENTRY_DSN"),
            integrations=[DjangoIntegration()],
            release=f"umurage@{VERSION}",
            environment=env("SENTRY_ENVIRONNEMENT", "developpement" if DEBUG else "production"),
            send_default_pii=False,  # ni noms, ni adresses IP, ni cookies
            traces_sample_rate=float(env("SENTRY_TRACES", "0")),
        )
    except ImportError:  # pragma: no cover
        import warnings

        warnings.warn("SENTRY_DSN est défini mais sentry-sdk n'est pas installé (pip install sentry-sdk).")
