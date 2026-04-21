from pathlib import Path
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me")

ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

INSTALLED_APPS = [
    "django_prometheus",
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
    "apps.document_collections",
    "apps.document_collection_users",
    "apps.document_collection_documents",
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

ROOT_URLCONF = "aura_document_collection_service.urls"

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

WSGI_APPLICATION = "aura_document_collection_service.wsgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

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
    }
}

SERVICE_API_KEY = config("SERVICE_API_KEY", default="change-me")

_auth_service_url = config("AUTHENTICATION_SERVICE_URL", default="").strip()
AUTHENTICATION_PROVIDER_URL = (
    _auth_service_url
    or config("AUTHENTICATION_PROVIDER_AUTHENTICATION_URL", default="").strip()
    or config("AUTHENTICATION_PROVIDER_URL", default="http://localhost:8000/api/v1/auth/me").strip()
)

USER_PROFILE_SERVICE_URL = config("USER_PROFILE_SERVICE_URL", default="http://localhost:8000").strip()
USER_PROFILE_SERVICE_TIMEOUT = float(config("USER_PROFILE_SERVICE_TIMEOUT", default="5.0"))
USER_PROFILE_CACHE_TTL_SECONDS = int(config("USER_PROFILE_CACHE_TTL_SECONDS", default="45"))
USER_PROFILE_STRICT = config("USER_PROFILE_STRICT", default="false").lower() in ("1", "true", "yes")
USER_PROFILE_MAX_RETRIES = int(config("USER_PROFILE_MAX_RETRIES", default="3"))
USER_PROFILE_BREAKER_FAIL_THRESHOLD = int(config("USER_PROFILE_BREAKER_FAIL_THRESHOLD", default="5"))
USER_PROFILE_BREAKER_OPEN_SECONDS = int(config("USER_PROFILE_BREAKER_OPEN_SECONDS", default="30"))

_redis_url = config("REDIS_URL", default="redis://127.0.0.1:6379/1").strip()
_cache_key_prefix = config("CACHE_KEY_PREFIX", default="aura-doc-collect:").strip()

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": _redis_url,
        "KEY_PREFIX": _cache_key_prefix,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": int(config("REDIS_MAX_CONNECTIONS", default="50")),
                "retry_on_timeout": True,
            },
            "IGNORE_EXCEPTIONS": True,
        },
    }
}

DEFAULT_LOCAL_CORS_ORIGINS: list[str] = [
    *[f"http://localhost:{port}" for port in range(8000, 8007)],
    *[f"http://127.0.0.1:{port}" for port in range(8000, 8007)],
]
RABBITMQ_MANAGER_URL = config("RABBITMQ_MANAGER_URL", default="http://localhost:15672").strip()

AUTHENTICATION_EXCLUDED_PATHS = [
    "/api/v1/health",
    "/metrics",
    "/admin/*",
    "/api/schema*",
    "/api/docs*",
    "/api/redoc*",
]

_cors_origins_raw = config("CORS_ORIGINS", default="").strip()
_cors_normalized = _cors_origins_raw.strip("[]").replace("'", '"').replace('"', "").strip()
if _cors_origins_raw in ("*", '["*"]', "['*']") or _cors_normalized == "*":
    CORS_ALLOW_ALL_ORIGINS = True
    CORS_ALLOWED_ORIGINS = []
elif not _cors_origins_raw:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = list(DEFAULT_LOCAL_CORS_ORIGINS)
else:
    CORS_ALLOW_ALL_ORIGINS = False
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

CORS_ALLOW_CREDENTIALS = True

THROTTLE_ANON_RATE = config("THROTTLE_ANON_RATE", default="30/minute")
THROTTLE_USER_RATE = config("THROTTLE_USER_RATE", default="120/minute")

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
        "anon": THROTTLE_ANON_RATE,
        "user": THROTTLE_USER_RATE,
    },
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Aura Document Collection Service",
    "DESCRIPTION": (
        "REST API for document collections and membership.\n\n"
        "**Authentication:** use **Authorization: Bearer** (validated by the auth service), "
        "or service-to-service headers **X-Service-Api-Key**, **X-User-Id**, and **X-User-Email** "
        "(optional: **X-User-Roles**, **X-User-Permissions**), as enforced by the authentication middleware.\n\n"
        "**HTTP semantics:** **401** is returned by the gateway middleware when credentials are missing or invalid. "
        "**403** with `error_code=insufficient_permissions` means the caller is authenticated but lacks "
        "application-level permissions for the operation."
    ),
    "VERSION": config("APP_VERSION", default="1.0.0"),
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Bearer token validated by the authentication service.",
            },
            "serviceApiKey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Service-Api-Key",
                "description": "Shared service API key (must match SERVICE_API_KEY).",
            },
            "serviceUserId": {
                "type": "apiKey",
                "in": "header",
                "name": "X-User-Id",
                "description": "Acting user id (integer) for service-to-service calls.",
            },
            "serviceUserEmail": {
                "type": "apiKey",
                "in": "header",
                "name": "X-User-Email",
                "description": "Acting user email for service-to-service calls.",
            },
            "serviceUserRoles": {
                "type": "apiKey",
                "in": "header",
                "name": "X-User-Roles",
                "description": "Optional comma-separated roles forwarded to downstream services.",
            },
            "serviceUserPermissions": {
                "type": "apiKey",
                "in": "header",
                "name": "X-User-Permissions",
                "description": "Optional comma-separated permission codes (application-level).",
            },
        },
    },
    "SECURITY": [
        {"bearerAuth": []},
        {
            "serviceApiKey": [],
            "serviceUserId": [],
            "serviceUserEmail": [],
        },
    ],
    "TAGS": [
        {"name": "Health", "description": "Service health"},
        {"name": "DocumentCollections", "description": "Document group CRUD"},
        {"name": "DocumentCollectionUsers", "description": "Users in a document collection"},
        {"name": "DocumentCollectionDocuments", "description": "Documents linked to a document collection"},
    ],
}

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
