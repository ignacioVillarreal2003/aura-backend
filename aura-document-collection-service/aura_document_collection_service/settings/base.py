from pathlib import Path
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config("SECRET_KEY")

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
    "apps.document_collection_documents",
    "apps.classification_levels",
    "apps.compartments",
    "apps.user_authorizations",
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

_db_connect_timeout = config("DB_CONNECT_TIMEOUT", default=5, cast=int)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT", default="5432"),
        "OPTIONS": {
            "connect_timeout": _db_connect_timeout,
        },
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
    }
}

AUTHENTICATION_PROVIDER_URL = config("AUTHENTICATION_SERVICE_URL").strip()
SERVICE_API_KEY = config("SERVICE_API_KEY", default="service_api_key").strip()
AUTH_TOKEN_CACHE_TTL_SECONDS = config("AUTH_TOKEN_CACHE_TTL_SECONDS", default=60, cast=int)
AUTH_SERVICE_TIMEOUT = config("AUTH_SERVICE_TIMEOUT", default=10, cast=float)


_redis_url = config("REDIS_URL").strip()
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

DEFAULT_PAGE_SIZE = config("DEFAULT_PAGE_SIZE", default=20, cast=int)
MAX_PAGE_SIZE = config("MAX_PAGE_SIZE", default=100, cast=int)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.service_authentication.ServiceAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.pagination.StandardPagination",
    "PAGE_SIZE": DEFAULT_PAGE_SIZE,
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
        "REST facade for modelling **Mandatory Access Control (MAC)** metadata around document collections:\n\n"
        "- classify collections with immutable-looking **classification levels** plus **compartments**,\n"
        "- maintain **membership rows** tying external document ids back to collections,\n"
        "- configure per-user **clearance** plus compartment badges that downstream services honor.\n\n"
        "### Consumers\n\n"
        "Operational UIs, automation jobs, or peer microservices that need to enumerate which collections "
        "a principal may touch - use **`GET .../accessible-collections/{user}`** once permissions allow.\n\n"
        "### Authentication (this schema)\n\n"
        "**Interactive / client credentials**: send `Authorization: Bearer <JWT>`. Tokens are validated against "
        "`AUTHENTICATION_SERVICE_URL` and populate `AuthenticatedUser.permissions` alongside roles/email.\n\n"
        "**Note:** server-to-server header authentication may still exist at runtime for internal gateways; "
        "it is intentionally **excluded from this OpenAPI document** so public Swagger exposes only Bearer.\n\n"
        "**401** originates from middleware when Bearer material is absent or JWT validation fails. "
        "**403 insufficient_permissions** (JSON `error`) means identity resolved but lacked the granular "
        "permission constants documented per route (see tag descriptions).\n\n"
        "### Operational headers & observability\n\n"
        "`X-Correlation-Id` is echoed on responses (generated if omitted) for tracing across mesh hops.\n\n"
        "### Pagination, filtering, sorting\n\n"
        "List endpoints are page-number paginated (`page`, optional `page_size` capped at **100**, default **20`). "
        "Where highlighted, Django Filter exposes query parameters enumerated on each route; Ordering uses `ordering=` "
        "with fields listed per resource.\n\n"
        "### Error envelope\n\n"
        "Unless the middleware emits a bespoke JSON blob first, handlers wrap failures as **`{ error, detail, "
        "status_code }`** (see reusable `ApiErrorBody` responses attached to statuses in this schema)."
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
                "description": (
                    "Standard `Authorization: Bearer <token>` header. The auth microservice validates the JWT and "
                    "returns `id`, `email`, `roles`, and `permissions` which feed `AccessControl` checks."
                ),
            },
        },
    },
    "SECURITY": [
        {"bearerAuth": []},
    ],
    "TAGS": [
        {
            "name": "Health",
            "description": (
                "Liveness-style probes that bypass auth middleware. Only `GET /api/v1/health` is described here; "
                "Prometheus metrics live at `/metrics` outside this tag."
            ),
        },
        {
            "name": "DocumentCollections",
            "description": (
                "CRUD for **document collections**—logical folders combining a **classification level** with one or "
                "more **compartments**. Deletes are soft; responses embed nested catalogue objects for convenience."
            ),
        },
        {
            "name": "ClassificationLevels",
            "description": (
                "MAC ladder maintenance: each record pairs a display `name` with a monotonic `rank` used for "
                "dominance checks. Protective rules block deletion while dependencies exist."
            ),
        },
        {
            "name": "Compartments",
            "description": (
                "Need-to-know silos orthogonal to rank. Collections reference many compartments; users gain "
                "membership rows that gate `accessible-collections` responses."
            ),
        },
        {
            "name": "UserAuthorizations",
            "description": (
                "Surface area for **per-user MAC state**: fetch aggregate authorization, set/delete clearance, "
                "CRUD compartment memberships, and query **pre-computed accessible collections** for cross-service "
                "enforcement."
            ),
        },
        {
            "name": "DocumentCollectionDocuments",
            "description": (
                "Nested routes under `/document-collections/{id}/documents` that **link** existing document records "
                "into a collection. Payloads never stream binaries—only registry ids and denormalized titles."
            ),
        },
    ],
}

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
