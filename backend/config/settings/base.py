import os
import sys
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR.parent / ".env")

if os.environ.get("IN_DOCKER", "False").lower() != "true":
    load_dotenv(BASE_DIR / ".env.local", override=True)


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set in the environment.")

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "accounts",
    "organizations",
    "support",
    "contacts",
    "conversations",
    "whatsapp",
    "templates",
    "automations",
    "flows",
    "pipelines",
    "leads",
    "broadcasts",
    "analytics",
    "realtime",
    "lead_collector",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
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
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB"),
        "USER": os.environ.get("POSTGRES_USER"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

if os.environ.get("USE_SQLITE_FOR_TESTS", "true").lower() == "true" and (
    "test" in sys.argv or os.environ.get("FORCE_SQLITE", "false").lower() == "true"
):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:" if os.environ.get("FORCE_SQLITE", "false").lower() == "true" else BASE_DIR / "test.sqlite3",
        }
    }

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "http://localhost:5173,http://localhost:8000")
SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "False").lower() == "true"
SESSION_COOKIE_SECURE = os.environ.get("DJANGO_SESSION_COOKIE_SECURE", "False").lower() == "true"
CSRF_COOKIE_SECURE = os.environ.get("DJANGO_CSRF_COOKIE_SECURE", "False").lower() == "true"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if os.environ.get("DJANGO_USE_X_FORWARDED_PROTO", "False").lower() == "true" else None

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("REDIS_URL", "redis://redis:6379/0")],
        },
    }
}

if "test" in sys.argv:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    }

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", os.environ.get("REDIS_URL", "redis://redis:6379/0"))
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
}

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Lead Collector provider limits are server-owned safety controls. Search depth
# profiles may lower these values but clients never submit execution budgets.
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")
GEOAPIFY_API_KEY = os.environ.get("GEOAPIFY_API_KEY", "")
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "")
ZOOMINFO_API_KEY = os.environ.get("ZOOMINFO_API_KEY", "")
OVERPASS_API_URLS = tuple(item.strip() for item in os.environ.get("OVERPASS_API_URLS", "").split(",") if item.strip())
OVERPASS_API_URL = os.environ.get("OVERPASS_API_URL", "").strip()
NOMINATIM_API_URL = os.environ.get("NOMINATIM_API_URL", "https://nominatim.openstreetmap.org/search")
PLAYWRIGHT_HEADLESS = os.environ.get("PLAYWRIGHT_HEADLESS", "true").casefold() not in {"0", "false", "no"}
PLAYWRIGHT_TIMEOUT = min(max(int(os.environ.get("PLAYWRIGHT_TIMEOUT", "15000")), 3000), 30000)
PLAYWRIGHT_MAX_RESULTS = min(max(int(os.environ.get("PLAYWRIGHT_MAX_RESULTS", "20")), 1), 50)
PLAYWRIGHT_MAX_RESULTS_PER_QUERY = min(max(int(os.environ.get("PLAYWRIGHT_MAX_RESULTS_PER_QUERY", "20")), 1), 50)
PLAYWRIGHT_MAX_TOTAL_RESULTS = min(max(int(os.environ.get("PLAYWRIGHT_MAX_TOTAL_RESULTS", "40")), 1), 100)
PLAYWRIGHT_GRID_ENABLED = os.environ.get("PLAYWRIGHT_GRID_ENABLED", "true").casefold() not in {"0", "false", "no"}
