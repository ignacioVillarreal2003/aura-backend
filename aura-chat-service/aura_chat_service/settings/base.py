from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

APP_NAME = "Aura Chat Service"
APP_VERSION = "1.0.0"

SECRET_KEY = config("SECRET_KEY")

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
    "apps.artifact_message",
    "apps.peer_message",
    "apps.membership",
    "apps.artifact_report",
    "apps.artifact_checklist",
    "apps.assistant",
    "apps.artifact",
    "apps.artifact_timeline",
    "apps.artifact_quiz",
    "apps.artifact_lessons_learned",
    "apps.artifact_decision_brief",
    "apps.artifact_document_summary",
    "apps.artifact_document_action",
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
            "hosts": [{"address": REDIS_URL, "socket_connect_timeout": 5}],
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
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True

AUTHENTICATION_SERVICE_URL = config("AUTHENTICATION_SERVICE_URL").strip()
AUTH_TOKEN_CACHE_TTL_SECONDS = config("AUTH_TOKEN_CACHE_TTL_SECONDS", default=60, cast=int)
AUTH_SERVICE_TIMEOUT = config("AUTH_SERVICE_TIMEOUT", default=10, cast=float)

AUDIO_MAX_UPLOAD_MB = config("AUDIO_MAX_UPLOAD_MB", default=25, cast=int)
DATA_UPLOAD_MAX_MEMORY_SIZE = config("DATA_UPLOAD_MAX_MEMORY_SIZE", default=30 * 1024 * 1024, cast=int)

WS_MAX_CONNECTIONS_PER_USER = config("WS_MAX_CONNECTIONS_PER_USER", default=5, cast=int)
WS_MESSAGE_RATE_LIMIT_MAX = config("WS_MESSAGE_RATE_LIMIT_MAX", default=10, cast=int)
WS_MESSAGE_RATE_LIMIT_WINDOW = config("WS_MESSAGE_RATE_LIMIT_WINDOW", default=60, cast=int)
WS_TYPING_RATE_LIMIT_MAX = config("WS_TYPING_RATE_LIMIT_MAX", default=20, cast=int)
WS_TYPING_RATE_LIMIT_WINDOW = config("WS_TYPING_RATE_LIMIT_WINDOW", default=10, cast=int)
WS_ARTIFACT_RATE_LIMIT_MAX = config("WS_ARTIFACT_RATE_LIMIT_MAX", default=5, cast=int)
WS_ARTIFACT_RATE_LIMIT_WINDOW = config("WS_ARTIFACT_RATE_LIMIT_WINDOW", default=60, cast=int)
WS_TRANSCRIBE_RATE_LIMIT_MAX = config("WS_TRANSCRIBE_RATE_LIMIT_MAX", default=5, cast=int)
WS_TRANSCRIBE_RATE_LIMIT_WINDOW = config("WS_TRANSCRIBE_RATE_LIMIT_WINDOW", default=60, cast=int)

# When Redis is unreachable the rate-limit checks fall back to this decision.
# True (default) favours availability (let traffic through); set False to fail
# closed and block on Redis errors instead (favours abuse protection).
WS_RATE_LIMIT_FAIL_OPEN = config("WS_RATE_LIMIT_FAIL_OPEN", default=True, cast=bool)

AUTHENTICATION_EXCLUDED_PATHS = [
    "/api/v1/health*",
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
            "description": "Liveness/readiness: chequeos de base de datos y Redis (`GET /api/v1/health`).",
        },
        {
            "name": "Chats",
            "description": (
                "Creación y gestión de chats: listado, CRUD, fijar, archivar, bloquear; "
                "incluye las colecciones `me` y `archived`."
            ),
        },
        {
            "name": "Messages",
            "description": (
                "Historial con paginación por cursor (`GET .../messages/`), envío con IA "
                "(`POST .../messages/generate/`), "
                "borrado y export por mensaje. `{message_id}` es el campo `id` de cada fila "
                "(no `artifact_id`). Bookmark, pin, feedback e hilos viven bajo **Artifacts**."
            ),
        },
        {
            "name": "Memberships",
            "description": "Listar/actualizar miembros, invitar usuarios, roles, abandonar chat.",
        },
        {
            "name": "Share Links",
            "description": (
                "Gestión autenticada de tokens de compartición; el listado de mensajes **público** "
                "de solo lectura usa `GET /api/v1/share/{token}/messages/` (AllowAny)."
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
                "Asistentes especializados configurables (equivalente a Custom GPTs). "
                "Los admins crean asistentes con system prompts fijos; "
                "los usuarios inician sesiones de chat pre-configuradas."
            ),
        },
        {
            "name": "Artifacts",
            "description": (
                "Capa documental unificada: cabecera `artifact` (type/mode/fragments). "
                "Interacciones por `artifact_id`: feedback, bookmark, pin, thread; "
                "listas de fijados/marcados por `chat_id`. Cada tipo (message, report, checklist, quiz, "
                "timeline, lessons learned, decision brief, document summary, document action) "
                "tiene endpoints dedicados bajo `/api/v1/`."
            ),
        },
        {
            "name": "Timelines",
            "description": (
                "Líneas de tiempo generadas con IA. Requiere `LLM_TIMELINE_GENERATE_URL`. "
                "Prefijo `/api/v1/timelines/`."
            ),
        },
        {
            "name": "Quizzes",
            "description": (
                "Cuestionarios generados con IA. Requiere `LLM_QUIZ_GENERATE_URL`. "
                "Prefijo `/api/v1/quizzes/`."
            ),
        },
        {
            "name": "Lessons Learned",
            "description": (
                "Lecciones aprendidas generadas con IA. Requiere `LLM_LESSONS_LEARNED_GENERATE_URL`. "
                "Prefijo `/api/v1/lessons-learned/`."
            ),
        },
        {
            "name": "Decision Briefs",
            "description": (
                "Briefs de decisión generados con IA. Requiere `LLM_DECISION_BRIEF_GENERATE_URL`. "
                "Prefijo `/api/v1/decision-briefs/`."
            ),
        },
        {
            "name": "Document Summaries",
            "description": (
                "Resúmenes de documentos generados con IA. Requiere `LLM_DOCUMENT_SUMMARY_URL`. "
                "Prefijo `/api/v1/document-summaries/`."
            ),
        },
        {
            "name": "Document Actions",
            "description": (
                "Acciones estructuradas sobre documentos ejecutadas con IA. Requiere `LLM_DOCUMENT_ACTION_URL`. "
                "Prefijo `/api/v1/document-actions/`."
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
                    "Usá Authorization Bearer con el JWT de tu proveedor de identidad. "
                    "Los claims deben incluir los permisos de aplicación requeridos por cada operación (p. ej. LIST_CHATS)."
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

WHISPER_PRELOAD = config("WHISPER_PRELOAD", default=False, cast=bool)

NOTIFICATION_SERVICE_URL = config("NOTIFICATION_SERVICE_URL").strip()
NOTIFICATION_INTERNAL_API_TOKEN = config("NOTIFICATION_INTERNAL_API_TOKEN")

DOCUMENT_PROCESSING_SERVICE_URL = config("DOCUMENT_PROCESSING_SERVICE_URL", default="").strip()
DOCUMENT_PROCESSING_SERVICE_TIMEOUT = config("DOCUMENT_PROCESSING_SERVICE_TIMEOUT", default=5, cast=int)

LLM_DOCUMENT_QUESTION_URL = config("LLM_DOCUMENT_QUESTION_URL").strip()
LLM_DOCUMENT_QUESTION_STREAM_URL = config("LLM_DOCUMENT_QUESTION_STREAM_URL").strip()
LLM_GENERAL_CHAT_URL = config("LLM_GENERAL_CHAT_URL").strip()
LLM_GENERAL_CHAT_STREAM_URL = config("LLM_GENERAL_CHAT_STREAM_URL").strip()
LLM_RAG_AGENT_URL = config("LLM_RAG_AGENT_URL").strip()
LLM_RAG_AGENT_STREAM_URL = config("LLM_RAG_AGENT_STREAM_URL").strip()
LLM_CHECKLIST_GENERATE_URL = config("LLM_CHECKLIST_GENERATE_URL").strip()
LLM_CHECKLIST_GENERATE_STREAM_URL = config("LLM_CHECKLIST_GENERATE_STREAM_URL", default="").strip()
LLM_REPORT_GENERATE_URL = config("LLM_REPORT_GENERATE_URL").strip()
LLM_REPORT_GENERATE_STREAM_URL = config("LLM_REPORT_GENERATE_STREAM_URL", default="").strip()
LLM_TIMELINE_GENERATE_URL = config("LLM_TIMELINE_GENERATE_URL", default="").strip()
LLM_TIMELINE_GENERATE_STREAM_URL = config("LLM_TIMELINE_GENERATE_STREAM_URL", default="").strip()
LLM_QUIZ_GENERATE_URL = config("LLM_QUIZ_GENERATE_URL", default="").strip()
LLM_QUIZ_GENERATE_STREAM_URL = config("LLM_QUIZ_GENERATE_STREAM_URL", default="").strip()
LLM_LESSONS_LEARNED_GENERATE_URL = config("LLM_LESSONS_LEARNED_GENERATE_URL", default="").strip()
LLM_LESSONS_LEARNED_GENERATE_STREAM_URL = config("LLM_LESSONS_LEARNED_GENERATE_STREAM_URL", default="").strip()
LLM_DECISION_BRIEF_GENERATE_URL = config("LLM_DECISION_BRIEF_GENERATE_URL", default="").strip()
LLM_DECISION_BRIEF_GENERATE_STREAM_URL = config("LLM_DECISION_BRIEF_GENERATE_STREAM_URL", default="").strip()
LLM_DOCUMENT_SUMMARY_URL = config("LLM_DOCUMENT_SUMMARY_URL", default="").strip()
LLM_DOCUMENT_SUMMARY_STREAM_URL = config("LLM_DOCUMENT_SUMMARY_STREAM_URL", default="").strip()
LLM_DOCUMENT_ACTION_URL = config("LLM_DOCUMENT_ACTION_URL", default="").strip()
LLM_DOCUMENT_ACTION_STREAM_URL = config("LLM_DOCUMENT_ACTION_STREAM_URL", default="").strip()
LLM_FEEDBACK_EVALUATION_URL = config("LLM_FEEDBACK_EVALUATION_URL", default="").strip()
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

_LOG_LEVEL = config("LOG_LEVEL", default="INFO")

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
        "level": _LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": _LOG_LEVEL,
            "propagate": False,
        },
        "core": {
            "handlers": ["console"],
            "level": _LOG_LEVEL,
            "propagate": False,
        },
        "daphne": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
