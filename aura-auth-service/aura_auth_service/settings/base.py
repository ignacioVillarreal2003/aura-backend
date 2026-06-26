"""
Base settings for the aura_auth_service project — shared across all environments.
Environment overrides live in development.py / production.py / test.py.

Environment-based configuration using python-decouple.
Database: PostgreSQL 17
Python: 3.13
Django: 5.x
"""

from pathlib import Path
from decouple import config, Csv

# Service root (3 levels up: settings/ -> aura_auth_service/ -> <service root>)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
# OFF by default; development.py turns it on, production.py keeps it off.
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost,host.docker.internal', cast=Csv())

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_prometheus',

    # Third-party apps
    'corsheaders',
    'rest_framework',
    'django_filters',
    'drf_spectacular',
    
    # Local apps
    'apps.accounts.apps.AccountsConfig',
    'apps.documents.apps.DocumentsConfig',
    'apps.notifications.apps.NotificationsConfig',
    'apps.chat.apps.ChatConfig',
]

# Local apps whose tables are owned by docker/auth-db/init.sql or docker/aura-db/init.sql.
# Setting to None disables Django migrations entirely for these apps.
_LOCAL_APPS = ['accounts', 'documents', 'notifications', 'chat']
MIGRATION_MODULES = {app: None for app in _LOCAL_APPS}

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'core.middleware.request_id.RequestIDMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'apps.accounts.middleware.bearer_token_middleware.BearerTokenMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'apps.accounts.middleware.elevation_middleware.ElevationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'aura_auth_service.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'aura_auth_service.wsgi.application'

# Database Configuration
# Default: PostgreSQL auth_db from docker-compose

DB_ENGINE = config('DB_ENGINE', default='django.db.backends.postgresql')

if DB_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': BASE_DIR / 'db.sqlite3',
        },
        'aura_db': {
            'ENGINE': DB_ENGINE,
            'NAME': BASE_DIR / 'aura_db.sqlite3',
        },
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': config('DB_NAME', default='auth_db'),
            'USER': config('DB_USER', default='aura_root'),
            'PASSWORD': config('DB_PASSWORD', default='aura_password'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5433'),
            'CONN_MAX_AGE': 600,
            'CONN_HEALTH_CHECKS': True,
            'OPTIONS': {
                'connect_timeout': 10,
                'options': '-c statement_timeout=30000'
            }
        },
        'aura_db': {
            'ENGINE': DB_ENGINE,
            'NAME': config('AURA_DB_NAME', default='aura_db', cast=str),
            'USER': config('AURA_DB_USER', default='aura_root', cast=str),
            'PASSWORD': config('AURA_DB_PASSWORD', default='aura_password', cast=str),
            'HOST': config('AURA_DB_HOST', default='localhost', cast=str),
            'PORT': config('AURA_DB_PORT', default='5432', cast=str),
            'CONN_MAX_AGE': 600,
            'CONN_HEALTH_CHECKS': True,
            'OPTIONS': {
                'connect_timeout': 10,
                'options': '-c statement_timeout=30000',
                'client_encoding': 'UTF8',
            }
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Database routers
DATABASE_ROUTERS = ['aura_auth_service.db_routers.AuraDbRouter']

# Cache configuration.
#  - default:     in-process (LocMem) — used by DRF throttling; behaviour unchanged.
#  - permissions: short-lived Redis cache of computed roles/permissions for the
#    /auth/validate hot path. Isolated in its own alias and Redis DB index so a
#    Redis outage degrades only this cache (callers fall back to a direct DB
#    compute) and never affects throttling.
PERMISSIONS_CACHE_TTL = config('PERMISSIONS_CACHE_TTL', default=60, cast=int)
PERMISSIONS_CACHE_REDIS_URL = config('PERMISSIONS_CACHE_REDIS_URL', default='redis://memory_db:6379/1')

# Dedicated Redis DB index (2) for DRF throttling so rate limits are shared and
# accurate across gunicorn workers (LocMem would be per-process). Isolated from
# the permissions cache (index 1). The throttles fail open on a Redis outage —
# see core.throttling — so this never becomes a hard dependency for auth.
THROTTLE_CACHE_REDIS_URL = config('THROTTLE_CACHE_REDIS_URL', default='redis://memory_db:6379/2')

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    },
    'permissions': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': PERMISSIONS_CACHE_REDIS_URL,
        'KEY_PREFIX': 'auth_perms',
        'TIMEOUT': PERMISSIONS_CACHE_TTL,
    },
    'throttle': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': THROTTLE_CACHE_REDIS_URL,
        'KEY_PREFIX': 'auth_throttle',
    },
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://localhost:4200', cast=Csv())

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'apps.accounts.authentication.JWTAuthentication',
        'apps.accounts.authentication.ServiceKeyAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'core.exceptions.handler.custom_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [],
    'DEFAULT_THROTTLE_RATES': {
        'login': config('LOGIN_RATE_LIMIT', default='5/minute'),
        'refresh': config('REFRESH_RATE_LIMIT', default='20/minute'),
        'change_password': config('CHANGE_PASSWORD_RATE_LIMIT', default='5/minute'),
        'user_lookup': config('USER_LOOKUP_RATE_LIMIT', default='60/minute'),
    },
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Aura Auth Service API',
    'DESCRIPTION': 'Authentication service: login, refresh, introspect and logout.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# JWT Configuration
JWT_ACCESS_LIFETIME_MINUTES = config('JWT_ACCESS_LIFETIME_MINUTES', default=15, cast=int)
JWT_ALGORITHM = config('JWT_ALGORITHM', default='HS256')
# JWT_SIGNING_KEY must be set independently — never share with SECRET_KEY
# Falls back to SECRET_KEY here; production.py enforces an explicit value.
JWT_SIGNING_KEY = config('JWT_SIGNING_KEY', default=None) or SECRET_KEY

# Login lockout policy
LOGIN_MAX_ATTEMPTS = config('LOGIN_MAX_ATTEMPTS', default=5, cast=int)
LOGIN_LOCKOUT_MINUTES = config('LOGIN_LOCKOUT_MINUTES', default=15, cast=int)

# Refresh token lifetime
REFRESH_TOKEN_LIFETIME_DAYS = config('REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)

# Document Processing Service
DOCUMENT_PROCESSING_URL = config(
    'DOCUMENT_PROCESSING_URL',
    default='http://localhost:8000',
)

# Shared key for *inbound* generic service-to-service calls (e.g. notification
# service enriching email recipients via the user lookup endpoint). Outbound
# inter-service calls forward/mint a JWT instead — see accounts.services.auth_service.
SERVICE_API_KEY = config('SERVICE_API_KEY', default='service_api_key')
DOCUMENT_PROCESSING_TIMEOUT_SECONDS = config(
    'DOCUMENT_PROCESSING_TIMEOUT_SECONDS',
    default=300,
    cast=int,
)

# Notification Service (used by Django admin notification flows)
NOTIFICATION_SERVICE_URL = config(
    'NOTIFICATION_SERVICE_URL',
    default='http://localhost:8004',
)
NOTIFICATION_INTERNAL_API_TOKEN = config(
    'NOTIFICATION_INTERNAL_API_TOKEN',
    default='dev-notification-internal-token',
)
NOTIFICATION_SERVICE_TIMEOUT_SECONDS = config(
    'NOTIFICATION_SERVICE_TIMEOUT_SECONDS',
    default=30,
    cast=int,
)

# Document Collection Service (MAC — Mandatory Access Control)
DOC_COLLECTION_SERVICE_URL = config('DOC_COLLECTION_SERVICE_URL', default='http://localhost:8005')

# Chat Service (used by Django admin Chat section: messages, share links, members)
CHAT_SERVICE_URL = config('CHAT_SERVICE_URL', default='http://localhost:8003')

# LLM Service — referenced only for the admin dashboard health panel today;
# no functional client exists yet (no admin feature reads from it directly).
LLM_SERVICE_URL = config('LLM_SERVICE_URL', default='http://localhost:8001')

# Dashboard health panel — per-service timeout for the concurrent health poll.
SERVICE_HEALTH_CHECK_TIMEOUT_SECONDS = config(
    'SERVICE_HEALTH_CHECK_TIMEOUT_SECONDS',
    default=3,
    cast=int,
)

# Neo4j HTTP API (dashboard graph stats)
NEO4J_HTTP_URL = config('NEO4J_HTTP_URL', default='http://neo4j:7474')
NEO4J_HTTP_USER = config('NEO4J_HTTP_USER', default='neo4j')
NEO4J_HTTP_PASSWORD = config('NEO4J_HTTP_PASSWORD', default='aura_password')

# RabbitMQ management API (dashboard queue depth)
RABBITMQ_MGMT_URL = config('RABBITMQ_MGMT_URL', default='http://queue:15672')
RABBITMQ_MGMT_USER = config('RABBITMQ_MGMT_USER', default='aura_root')
RABBITMQ_MGMT_PASSWORD = config('RABBITMQ_MGMT_PASSWORD', default='aura_password')

# Logging Configuration
_LOG_LEVEL = config('LOG_LEVEL', default='INFO')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(levelname)s %(name)s %(module)s %(request_id)s %(message)s'
        },
    },
    'filters': {
        'request_id': {
            '()': 'core.middleware.request_id.RequestIDLogFilter',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
            'filters': ['request_id'],
        },
    },
    'root': {
        'handlers': ['console'],
        'level': _LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'daphne': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Environment
ENVIRONMENT = config('ENVIRONMENT', default='development')

# Session — 1 hour for admin/superadmin panel
SESSION_COOKIE_AGE = 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Trust the reverse-proxy (nginx gateway) X-Forwarded-Proto header so Django
# detects HTTPS correctly behind the gateway. Harmless under DEBUG. The gateway
# already forwards this header (see aura-gateway/nginx.conf).
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
