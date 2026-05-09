from pathlib import Path

from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

APP_NAME = "Aura Notification Service"
APP_VERSION = "1.0.0"

SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me-in-production")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django_extensions",
    "corsheaders",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "django_prometheus",
    "apps.notification.apps.NotificationConfig",
]

_LOCAL_APPS = ["notification"]
MIGRATION_MODULES = {app: None for app in _LOCAL_APPS}

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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

ROOT_URLCONF = "aura_notification_service.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "aura_notification_service.wsgi.application"
ASGI_APPLICATION = "aura_notification_service.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": config("DB_ENGINE", default="django.db.backends.postgresql"),
        "NAME": config("DB_NAME", default="aura_db"),
        "USER": config("DB_USER", default="aura_root"),
        "PASSWORD": config("DB_PASSWORD", default="aura_password"),
        "HOST": config("DB_HOST", default="127.0.0.1"),
        "PORT": config("DB_PORT", default="5432"),
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
        "OPTIONS": {
            "connect_timeout": config("DB_CONNECT_TIMEOUT", default=5, cast=int),
            "options": "-c statement_timeout=30000",
        },
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:3000",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.service_authentication.ServiceAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
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
        "user": "240/minute",
    },
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": APP_NAME,
    "DESCRIPTION": (
        "Centralised notification API used by every aura microservice. "
        "Producers POST semantic events to `/api/v1/internal/events/`; "
        "the service materialises in-app notifications and dispatches "
        "email through a Celery worker, honouring per-user channel "
        "preferences, quiet hours and global mute. End users consume "
        "notifications through `/api/v1/notifications/` and receive "
        "real-time pushes via Server-Sent Events at "
        "`/api/v1/notifications/stream/`."
    ),
    "VERSION": APP_VERSION,
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "TAGS": [
        {"name": "Health", "description": "Liveness checks for DB / Redis / RabbitMQ."},
        {"name": "Notifications", "description": "End-user notification inbox: list, mark read, archive, delete."},
        {"name": "Realtime", "description": "Server-Sent Events stream of notification deltas."},
        {"name": "Preferences", "description": "Per-user global and per-event channel preferences."},
        {"name": "Event Types", "description": "Public catalogue of supported notification event types."},
        {"name": "Internal", "description": "Service-to-service endpoints (require `X-Internal-Token`)."},
    ],
    "SECURITY": [{"BearerAuth": []}],
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            },
            "InternalToken": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Internal-Token",
            },
        },
    },
    "ENUM_GENERATE_CHOICE_DESCRIPTION": True,
}

# -----------------------------------------------------------------------------
# Authentication
# -----------------------------------------------------------------------------
AUTHENTICATION_SERVICE_URL = config(
    "AUTHENTICATION_SERVICE_URL",
    default=config("AUTH_SERVICE_URL", default="http://127.0.0.1:8080"),
).strip()
SERVICE_API_KEY = config("SERVICE_API_KEY", default="dev-service-api-key")
NOTIFICATION_INTERNAL_API_TOKEN = config(
    "NOTIFICATION_INTERNAL_API_TOKEN",
    default="dev-notification-internal-token",
)
AUTH_TOKEN_CACHE_TTL_SECONDS = config(
    "AUTH_TOKEN_CACHE_TTL_SECONDS",
    default=60,
    cast=int,
)

AUTHENTICATION_EXCLUDED_PATHS = [
    "/api/v1/health",
    "/metrics",
    "/admin/*",
    "/api/schema*",
    "/api/docs*",
    "/api/redoc*",
    "/api/v1/internal/*",
    "/api/internal/*",
    "/api/v1/event-types/",
]

# -----------------------------------------------------------------------------
# Redis (cache + pub/sub for SSE)
# -----------------------------------------------------------------------------
REDIS_URL = config("REDIS_URL", default="redis://127.0.0.1:6379/2")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# -----------------------------------------------------------------------------
# Celery (broker = RabbitMQ, results = Redis)
# -----------------------------------------------------------------------------
CELERY_BROKER_URL = config(
    "CELERY_BROKER_URL",
    default="amqp://aura_root:aura_password@127.0.0.1:5672//",
)
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND",
    default="redis://127.0.0.1:6379/3",
)
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_DEFAULT_QUEUE = "notifications"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60
CELERY_TASK_SOFT_TIME_LIMIT = 45
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = "UTC"

# -----------------------------------------------------------------------------
# Email
# -----------------------------------------------------------------------------
EMAIL_BACKEND = config(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=25, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_TIMEOUT = config("EMAIL_TIMEOUT", default=10, cast=int)
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default="Aura <no-reply@aura.local>",
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# -----------------------------------------------------------------------------
# Notification subsystem
# -----------------------------------------------------------------------------
NOTIFICATION_HARD_DELETE_DAYS = config("NOTIFICATION_HARD_DELETE_DAYS", default=90, cast=int)
NOTIFICATION_DEFAULT_LINK_BASE_URL = config(
    "NOTIFICATION_DEFAULT_LINK_BASE_URL",
    default="http://localhost:3000",
)
NOTIFICATION_SSE_HEARTBEAT_SECONDS = config(
    "NOTIFICATION_SSE_HEARTBEAT_SECONDS",
    default=15,
    cast=int,
)
NOTIFICATION_SSE_MAX_DURATION_SECONDS = config(
    "NOTIFICATION_SSE_MAX_DURATION_SECONDS",
    default=60 * 30,
    cast=int,
)
NOTIFICATION_REDIS_CHANNEL_PREFIX = config(
    "NOTIFICATION_REDIS_CHANNEL_PREFIX",
    default="notif:user",
)

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(correlation_id)s %(message)s",
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
        "file": {
            "class": "logging.FileHandler",
            "filename": LOGS_DIR / "debug.log",
            "formatter": "verbose",
            "filters": ["correlation_id"],
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "core": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

ENVIRONMENT = config("ENVIRONMENT", default="development")
