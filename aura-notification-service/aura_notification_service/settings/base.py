from pathlib import Path
from decouple import AutoConfig, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

config = AutoConfig(search_path=str(BASE_DIR))

APP_NAME = "Aura Notification Service"
APP_VERSION = "1.0.0"

SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default=(
        "127.0.0.1,localhost,"
        "127.0.0.1:8000,127.0.0.1:8001,127.0.0.1:8002,127.0.0.1:8003,127.0.0.1:8004,"
        "localhost:8000,localhost:8001,localhost:8002,localhost:8003,localhost:8004"
    ),
    cast=Csv(),
)
_LOG_LEVEL = config("LOG_LEVEL", default="INFO")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
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

# Disable migrations for apps whose tables are not needed in this service.
MIGRATION_MODULES = {
    "notification": None,
    "auth": None,
    "contenttypes": None,
}

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.middleware.correlation_id.CorrelationIdMiddleware",
    "core.middleware.request_logging.RequestLoggingMiddleware",
    "core.authentication.authentication_middleware.AuthenticationMiddleware",
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
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "aura_notification_service.wsgi.application"
ASGI_APPLICATION = "aura_notification_service.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": config("DB_ENGINE", default="django.db.backends.postgresql"),
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
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
    default="http://localhost:3000,http://localhost:4200",
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
        "user": "240/minute",
        "internal": "120/minute",
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
    "ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE": False,
}

AUTHENTICATION_SERVICE_URL = config("AUTHENTICATION_SERVICE_URL").strip()
AUTH_USER_LOOKUP_URL = config("AUTH_USER_LOOKUP_URL").strip()
SERVICE_API_KEY = config("SERVICE_API_KEY")
NOTIFICATION_INTERNAL_API_TOKEN = config("NOTIFICATION_INTERNAL_API_TOKEN")
AUTH_TOKEN_CACHE_TTL_SECONDS = config(
    "AUTH_TOKEN_CACHE_TTL_SECONDS",
    default=60,
    cast=int,
)

AUTHENTICATION_EXCLUDED_PATHS = [
    "/api/v1/health",
    "/metrics",
    "/api/schema*",
    "/api/docs*",
    "/api/redoc*",
    "/api/v1/internal/*",
    "/api/v1/event-types/",
]

REDIS_URL = config("REDIS_URL")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

CELERY_BROKER_URL = config("CELERY_BROKER_URL").strip()
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND").strip()
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_DEFAULT_QUEUE = "notifications"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60
CELERY_TASK_SOFT_TIME_LIMIT = 45
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TIMEZONE = "UTC"

from kombu import Exchange as _Exchange, Queue as _Queue

_notifications_dlx = _Exchange("notifications.dlx", type="direct")
CELERY_QUEUES = (
    _Queue(
        "notifications",
        _Exchange("notifications", type="direct"),
        routing_key="notifications",
        queue_arguments={
            "x-dead-letter-exchange": "notifications.dlx",
            "x-dead-letter-routing-key": "notifications.dlq",
        },
    ),
    _Queue(
        "notifications.dlq",
        _notifications_dlx,
        routing_key="notifications.dlq",
    ),
)

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

NOTIFICATION_DEFAULT_LINK_BASE_URL = config("NOTIFICATION_DEFAULT_LINK_BASE_URL")
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

ENVIRONMENT = config("ENVIRONMENT", default="development")
