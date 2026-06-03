from pathlib import Path

from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

APP_NAME = "Aura Chat Service"
APP_VERSION = "1.0.0"

SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me")

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

INSTALLED_APPS = [
    "daphne",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "channels",
    "django_prometheus",
    "apps.chat",
    "apps.message",
    "apps.membership",
    "apps.report",
    "apps.checklist",
    "apps.assistant",
    "apps.artifact",
    "apps.timeline",
    "apps.quiz",
    "apps.lessons_learned",
    "apps.decision_brief",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.middleware.correlation_id.CorrelationIdMiddleware",
    "core.middleware.request_logging.RequestLoggingMiddleware",
    "core.authentication.authentication_middleware.AuthenticationMiddleware",
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
            ],
        },
    },
]

ASGI_APPLICATION = "aura_chat_service.asgi.application"

_db_connect_timeout = config("DB_CONNECT_TIMEOUT", default=5, cast=int)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT"),
        "OPTIONS": {
            "connect_timeout": _db_connect_timeout,
        },
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REDIS_URL = config("REDIS_URL")

CHAT_AI_REPLY_LOCK_TTL_SECONDS = config(
    "CHAT_AI_REPLY_LOCK_TTL_SECONDS",
    default=300,
    cast=int,
)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [{"address": REDIS_URL, "socket_timeout": None, "socket_connect_timeout": 5}],
            "expiry": 300,
        },
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

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

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000,http://localhost:4200",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

AUTHENTICATION_SERVICE_URL = config("AUTHENTICATION_SERVICE_URL").strip()
SERVICE_API_KEY = config("SERVICE_API_KEY")
AUTH_TOKEN_CACHE_TTL_SECONDS = config("AUTH_TOKEN_CACHE_TTL_SECONDS", default=60, cast=int)
AUTH_SERVICE_TIMEOUT = config("AUTH_SERVICE_TIMEOUT", default=10, cast=float)

AUDIO_MAX_UPLOAD_MB = config("AUDIO_MAX_UPLOAD_MB", default=25, cast=int)

WS_MAX_CONNECTIONS_PER_USER = config("WS_MAX_CONNECTIONS_PER_USER", default=5, cast=int)

AUTHENTICATION_EXCLUDED_PATHS = [
    "/api/v1/health",
    "/metrics",
    "/api/schema*",
    "/api/docs*",
    "/api/redoc*",
    "/api/v1/share/*",
]

SPECTACULAR_SETTINGS = {
    "TITLE": APP_NAME,
    "DESCRIPTION": (
        "REST API under `/api/v1/` for **chats**, **messages**, **memberships**, and **share links**. "
        "Most operations require `Authorization: Bearer <JWT>` and **application permissions** on the authenticated "
        "user (e.g. `LIST_CHATS`, `SEND_MESSAGE`) enforced per endpoint. "
        "See also Markdown docs in the repository `docs/` folder.\n\n"
        "- **Open JSON schema:** `GET /api/schema/`\n"
        "- **Swagger UI:** `GET /api/docs/`\n"
        "- **ReDoc:** `GET /api/redoc/`\n\n"
        "Public routes (no Bearer): health, schema/docs, read-only share by token (`/api/v1/share/...`). "
        "Real-time chat uses WebSockets separately from this OpenAPI surface."
    ),
    "VERSION": APP_VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {
            "name": "Health",
            "description": "Liveness/readiness: database and Redis checks (`GET /api/v1/health`).",
        },
        {
            "name": "Chats",
            "description": (
                "Create and manage chats: listing, CRUD, pin, archive, lock, mute; "
                "includes `me` and `archived` collections."
            ),
        },
        {
            "name": "Messages",
            "description": (
                "Message history (cursor pagination), send text/audio, bookmarks, pins, threads, feedback, "
                "exports, regenerate AI response, clear history, mark read."
            ),
        },
        {
            "name": "Memberships",
            "description": "List/update members, invite users, roles, leave chat.",
        },
        {
            "name": "Share Links",
            "description": (
                "Authenticated management of share tokens; **public** read-only message list uses "
                "`GET /api/v1/share/{token}/messages/` (AllowAny)."
            ),
        },
        {
            "name": "Reports",
            "description": (
                "Creación, listado, detalle, actualización y eliminación de informes estandarizados "
                "(SITREP, INTSUM, OPORD). Incluye exportación en PDF y Markdown."
            ),
        },
        {
            "name": "Checklists",
            "description": (
                "Generación, listado, detalle, actualización y eliminación de checklists de procedimientos. "
                "Soporta marcado de ítems y exportación en PDF y Markdown."
            ),
        },
        {
            "name": "Assistants",
            "description": (
                "Asistentes especializados configurables (Custom GPTs equivalent). "
                "Los admins crean asistentes con system prompts fijos; "
                "los usuarios inician sesiones de chat pre-configuradas."
            ),
        },
        {
            "name": "Artifacts",
            "description": (
                "Capa documental unificada: cabecera `artifact` (type/title/status/version) con "
                "versionado y referencias desde mensajes. Cada tipo (report, checklist, course, "
                "quiz, timeline, lessons learned) tiene su tabla especializada relacional."
            ),
        },
    ],
    "SECURITY": [{"BearerAuth": []}],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": (
                    "Use Authorization Bearer with the JWT from your identity provider. "
                    "Claims must include application permission strings required by each operation (e.g. LIST_CHATS)."
                ),
            },
        },
    },
    "ENUM_GENERATE_CHOICE_DESCRIPTION": True,
    "ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE": False,
}

WHISPER_MODEL_SIZE = config("WHISPER_MODEL_SIZE", default="small")
WHISPER_DEVICE = config("WHISPER_DEVICE", default="cpu")
WHISPER_COMPUTE_TYPE = config("WHISPER_COMPUTE_TYPE", default="int8")

WHISPER_MAX_CONCURRENCY = config("WHISPER_MAX_CONCURRENCY", default=2, cast=int)

NOTIFICATION_SERVICE_URL = config("NOTIFICATION_SERVICE_URL").strip()
NOTIFICATION_INTERNAL_API_TOKEN = config("NOTIFICATION_INTERNAL_API_TOKEN")

LLM_DOCUMENT_QUESTION_URL = config("LLM_DOCUMENT_QUESTION_URL").strip()
LLM_DOCUMENT_QUESTION_STREAM_URL = config("LLM_DOCUMENT_QUESTION_STREAM_URL").strip()
LLM_GENERAL_CHAT_URL = config("LLM_GENERAL_CHAT_URL").strip()
LLM_GENERAL_CHAT_STREAM_URL = config("LLM_GENERAL_CHAT_STREAM_URL").strip()
LLM_RAG_AGENT_URL = config("LLM_RAG_AGENT_URL").strip()
LLM_RAG_AGENT_STREAM_URL = config("LLM_RAG_AGENT_STREAM_URL").strip()
LLM_AGENT_URL = config("LLM_AGENT_URL").strip()
LLM_AGENT_STREAM_URL = config("LLM_AGENT_STREAM_URL").strip()
LLM_CHECKLIST_GENERATE_URL = config("LLM_CHECKLIST_GENERATE_URL").strip()
LLM_REPORT_GENERATE_URL = config("LLM_REPORT_GENERATE_URL").strip()
# New artifact generators. Defaulted to "" so the service still boots when the
# corresponding LLM endpoints are not yet wired in the environment.
LLM_TIMELINE_GENERATE_URL = config("LLM_TIMELINE_GENERATE_URL", default="").strip()
LLM_QUIZ_GENERATE_URL = config("LLM_QUIZ_GENERATE_URL", default="").strip()
LLM_LESSONS_LEARNED_GENERATE_URL = config("LLM_LESSONS_LEARNED_GENERATE_URL", default="").strip()
LLM_DECISION_BRIEF_GENERATE_URL = config("LLM_DECISION_BRIEF_GENERATE_URL", default="").strip()
LLM_SERVICE_TIMEOUT = config("LLM_SERVICE_TIMEOUT", default=120, cast=int)
LLM_STREAM_CONNECT_TIMEOUT = config(
    "LLM_STREAM_CONNECT_TIMEOUT", default=10.0, cast=float
)
LLM_STREAM_READ_TIMEOUT = config(
    "LLM_STREAM_READ_TIMEOUT", default=180.0, cast=float
)
LLM_CONTEXT_MESSAGE_LIMIT = config("LLM_CONTEXT_MESSAGE_LIMIT", default=10, cast=int)

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

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
