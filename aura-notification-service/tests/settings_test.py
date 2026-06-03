SECRET_KEY = "test-secret-key-not-used-in-production"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django_extensions",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "apps.notification.apps.NotificationConfig",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
    "core.middleware.correlation_id.CorrelationIdMiddleware",
    "core.middleware.request_logging.RequestLoggingMiddleware",
    "core.authentication.authentication_middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "aura_notification_service.urls"

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

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
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
    "DEFAULT_THROTTLE_CLASSES": [],
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
    "TITLE": "Aura Notification Service",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE": False,
}

SERVICE_API_KEY = "test-service-key"
AUTHENTICATION_SERVICE_URL = "http://auth-service.test/auth/validate"
AUTH_USER_LOOKUP_URL = "http://auth-service.test/auth/users/lookup"
NOTIFICATION_INTERNAL_API_TOKEN = "test-internal-token"
AUTH_TOKEN_CACHE_TTL_SECONDS = 60

AUTHENTICATION_EXCLUDED_PATHS = [
    "/api/v1/health",
    "/metrics",
    "/api/schema*",
    "/api/docs*",
    "/api/redoc*",
    "/api/v1/internal/*",
    "/api/v1/event-types/",
]

REDIS_URL = "redis://localhost:6379/15"

CELERY_BROKER_URL = "memory://"
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "Test <no-reply@test.local>"
SERVER_EMAIL = DEFAULT_FROM_EMAIL

NOTIFICATION_DEFAULT_LINK_BASE_URL = "https://app.test"
NOTIFICATION_SSE_HEARTBEAT_SECONDS = 15
NOTIFICATION_SSE_MAX_DURATION_SECONDS = 1800
NOTIFICATION_REDIS_CHANNEL_PREFIX = "notif:user"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "null": {"class": "logging.NullHandler"},
    },
    "root": {"handlers": ["null"], "level": "CRITICAL"},
}
