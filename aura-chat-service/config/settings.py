"""Django settings for the Aura Chat Service.

All tuneable values are read from environment variables so this file can be
committed safely and deployments only need an .env file (or env injection).
"""

import os

import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-key")

DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# Explicit comma-separated list for production; '*' only acceptable behind a
# trusted reverse proxy that enforces Host validation at the network layer.
_allowed = os.environ.get("ALLOWED_HOSTS", "*")
ALLOWED_HOSTS: list[str] = _allowed.split(",") if _allowed != "*" else ["*"]

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "corsheaders",
    "chat",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default="postgresql://aura_root:aura_password@localhost:5432/aura_db",
        conn_max_age=600,
    )
}

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "chat.auth.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "chat.exceptions.custom_exception_handler",
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = True

# ---------------------------------------------------------------------------
# External services
# ---------------------------------------------------------------------------

AUTH_SERVICE_URL = os.environ.get("AUTH_SERVICE_URL", "http://localhost:8080")

LLM_SERVICE_URL = os.environ.get("LLM_SERVICE_URL", "http://localhost:8001")
LLM_TIMEOUT_SECONDS = int(os.environ.get("LLM_TIMEOUT_SECONDS", "120"))

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_MESSAGES_PER_MINUTE = int(os.environ.get("RATE_LIMIT_MESSAGES_PER_MINUTE", "30"))
RATE_LIMIT_CONVERSATIONS_PER_MINUTE = int(os.environ.get("RATE_LIMIT_CONVERSATIONS_PER_MINUTE", "10"))

# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

DEFAULT_PAGE_SIZE = int(os.environ.get("DEFAULT_PAGE_SIZE", "20"))
MAX_PAGE_SIZE = int(os.environ.get("MAX_PAGE_SIZE", "100"))
MAX_MESSAGES_PAGE_SIZE = int(os.environ.get("MAX_MESSAGES_PAGE_SIZE", "200"))

# ---------------------------------------------------------------------------
# i18n / timezone
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG" if DEBUG else "INFO",
    },
    "loggers": {
        "django": {"level": "WARNING"},
        "daphne": {"level": "WARNING"},
    },
}
