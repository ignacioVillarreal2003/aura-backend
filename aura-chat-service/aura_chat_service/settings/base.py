from pathlib import Path

from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me")

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "channels",
    "django_prometheus",
    "apps.chat",
    "apps.message",
    "apps.membership",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.middleware.correlation_id.CorrelationIdMiddleware",
    "core.middleware.request_logging.RequestLoggingMiddleware",
    "core.authentication.authentication_middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "aura_chat_service.urls"

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

ASGI_APPLICATION = "aura_chat_service.asgi.application"

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="aura_db"),
        "USER": config("DB_USER", default="aura_root"),
        "PASSWORD": config("DB_PASSWORD", default="aura_password"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "OPTIONS": {
            "connect_timeout": 5,
        },
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ──────────────────────────────────────────────
# Redis (Channels + distributed chat AI reply lock)
# ──────────────────────────────────────────────

REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CHAT_AI_REPLY_LOCK_TTL_SECONDS = config(
    "CHAT_AI_REPLY_LOCK_TTL_SECONDS",
    default=180,
    cast=int,
)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}

# ──────────────────────────────────────────────
# Django REST Framework
# ──────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.service_authentication.ServiceAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "core.exceptions.handler.custom_exception_handler",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "120/minute",
    },
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# ──────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

# ──────────────────────────────────────────────
# Authentication service
# ──────────────────────────────────────────────
# The provider issues GET requests with ``Authorization: Bearer <token>`` to this URL
# (see ``core.authentication.authentication_provider.AuthenticationProvider.validate_token``).
# ``AUTHENTICATION_PROVIDER_AUTHENTICATION_URL`` is accepted as a fallback name so
# local mocks match other services' env naming.

_auth_service_url = config("AUTHENTICATION_SERVICE_URL", default="").strip()
AUTHENTICATION_SERVICE_URL = _auth_service_url or config(
    "AUTHENTICATION_PROVIDER_AUTHENTICATION_URL",
    default="http://auth-service:8000/api/v1/auth/me",
).strip()
SERVICE_API_KEY = config("SERVICE_API_KEY", default="change-me")

AUTHENTICATION_EXCLUDED_PATHS = [
    "/api/v1/health",
    "/metrics",
    "/admin/*",
    "/api/schema*",
    "/api/docs*",
    "/api/redoc*",
]

SPECTACULAR_SETTINGS = {
    "TITLE": "Aura Chat Service",
    "DESCRIPTION": (
        "REST API for chats, messages, and memberships. "
        "Use **Authorization: Bearer** plus your token (validated by the auth service), "
        "or for service-to-service calls send **X-Service-Api-Key** with **X-User-Id**, "
        "**X-User-Email**, and optionally **X-User-Roles** / **X-User-Permissions**."
    ),
    "VERSION": config("APP_VERSION", default="1.0.0"),
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Health", "description": "Service health"},
        {"name": "Chats", "description": "Chat CRUD"},
        {"name": "Messages", "description": "Chat messages (REST)"},
        {"name": "Memberships", "description": "Chat members"},
    ],
    "SECURITY": [{"BearerAuth": []}, {"ServiceApiKey": []}],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Token de usuario validado por el auth service.",
            },
            "ServiceApiKey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Service-Api-Key",
                "description": "Clave para llamadas service-to-service. Requiere también X-User-Id y X-User-Email.",
            },
        }
    },
}

# ──────────────────────────────────────────────
# Whisper (transcripción local de audio)
# ──────────────────────────────────────────────

WHISPER_MODEL_SIZE = config("WHISPER_MODEL_SIZE", default="small")
WHISPER_DEVICE = config("WHISPER_DEVICE", default="cpu")
WHISPER_COMPUTE_TYPE = config("WHISPER_COMPUTE_TYPE", default="int8")

# ──────────────────────────────────────────────
# LLM Service
# ──────────────────────────────────────────────

LLM_DOCUMENT_QUESTION_URL = config(
    "LLM_DOCUMENT_QUESTION_URL",
    default="http://localhost:8001/api/v1/document-question",
)
# SSE streaming endpoint (chat service → LLM). Defaults to ``<LLM_DOCUMENT_QUESTION_URL>/stream``.
LLM_DOCUMENT_QUESTION_STREAM_URL = config(
    "LLM_DOCUMENT_QUESTION_STREAM_URL",
    default=LLM_DOCUMENT_QUESTION_URL.rstrip("/") + "/stream",
)
LLM_SERVICE_TIMEOUT = config("LLM_SERVICE_TIMEOUT", default=120, cast=int)
# Connect timeout for the streaming client; read timeout is unset (long generations).
LLM_STREAM_CONNECT_TIMEOUT = config(
    "LLM_STREAM_CONNECT_TIMEOUT", default=10.0, cast=float
)
LLM_STREAM_READ_TIMEOUT = config(
    "LLM_STREAM_READ_TIMEOUT", default=180.0, cast=float
)
LLM_CONTEXT_MESSAGE_LIMIT = config("LLM_CONTEXT_MESSAGE_LIMIT", default=20, cast=int)

# ──────────────────────────────────────────────
# Internationalization
# ──────────────────────────────────────────────

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ──────────────────────────────────────────────
# Static files
# ──────────────────────────────────────────────

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ──────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(correlation_id)s %(message)s"
        },
        "simple": {
            "format": "[{asctime}] [{levelname}] {message}",
            "style": "{",
        },
    },
    "filters": {
        "correlation_id": {
            "()": "core.middleware.correlation_id.CorrelationIdFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["correlation_id"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "core": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
