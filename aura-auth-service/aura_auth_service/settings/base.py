"""Configuracion base, compartida por todos los entornos."""

from pathlib import Path
from decouple import config, Csv
from django.core.exceptions import ImproperlyConfigured
import ldap
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost,host.docker.internal', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_prometheus',

    'corsheaders',
    'rest_framework',
    'django_filters',
    'drf_spectacular',

    'apps.accounts.apps.AccountsConfig',
    'apps.documents.apps.DocumentsConfig',
    'apps.notifications.apps.NotificationsConfig',
    'apps.chat.apps.ChatConfig',
]

# Las tablas de estas apps las crea init.sql, no las migraciones de Django
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

LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

DATABASE_ROUTERS = ['aura_auth_service.db_routers.AuraDbRouter']

PERMISSIONS_CACHE_TTL = config('PERMISSIONS_CACHE_TTL', default=60, cast=int)
PERMISSIONS_CACHE_REDIS_URL = config('PERMISSIONS_CACHE_REDIS_URL', default='redis://memory_db:6379/1')

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

from django_auth_ldap.config import LDAPSearch

AUTH_LDAP_SERVER_URI    = config('LDAP_SERVER_URI', default='ldap://localhost:389')
AUTH_LDAP_BIND_DN       = config('LDAP_BIND_DN', default='cn=admin,dc=aura,dc=local')
AUTH_LDAP_BIND_PASSWORD = config('LDAP_BIND_PASSWORD', default='admin_password')

_ldap_uid_attr = config('LDAP_ATTR_UID', default='uid')
AUTH_LDAP_USER_SEARCH = LDAPSearch(
    config('LDAP_USER_SEARCH_BASE', default='ou=users,dc=aura,dc=local'),
    ldap.SCOPE_SUBTREE,
    f'({_ldap_uid_attr}=%(user)s)',
)

LDAP_ATTR_UID                  = _ldap_uid_attr
LDAP_ATTR_MAIL                 = config('LDAP_ATTR_MAIL', default='mail')
LDAP_ATTR_DISPLAY_NAME         = config('LDAP_ATTR_DISPLAY_NAME', default='displayName')
LDAP_ATTR_CLASSIFICATION_LEVEL = config('LDAP_ATTR_CLASSIFICATION_LEVEL', default='auraClassificationLevel')
LDAP_ATTR_COMPARTMENT          = config('LDAP_ATTR_COMPARTMENT', default='auraCompartment')
LDAP_EMAIL_FALLBACK_DOMAIN     = config('LDAP_EMAIL_FALLBACK_DOMAIN', default='ldap.local')

LDAP_ATTR_ROLE                 = config('LDAP_ATTR_ROLE', default='employeeType')
LDAP_ROLE_ADMIN_VALUE          = config('LDAP_ROLE_ADMIN_VALUE', default='admin')

AUTH_LDAP_USER_ATTR_MAP = {
    'email': LDAP_ATTR_MAIL,
    'name':  LDAP_ATTR_DISPLAY_NAME,
}
AUTH_LDAP_ALWAYS_UPDATE_USER = True

AUTHENTICATION_BACKENDS = [
    'apps.accounts.ldap_backend.AuraLDAPBackend',
    'django.contrib.auth.backends.ModelBackend',
]

CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://localhost:4200', cast=Csv())

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

JWT_ACCESS_LIFETIME_MINUTES = config('JWT_ACCESS_LIFETIME_MINUTES', default=15, cast=int)
JWT_ALGORITHM = config('JWT_ALGORITHM', default='HS256')
JWT_SIGNING_KEY = config('JWT_SIGNING_KEY', default=None) or SECRET_KEY

LOGIN_MAX_ATTEMPTS = config('LOGIN_MAX_ATTEMPTS', default=5, cast=int)
LOGIN_LOCKOUT_MINUTES = config('LOGIN_LOCKOUT_MINUTES', default=15, cast=int)

REFRESH_TOKEN_LIFETIME_DAYS = config('REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)

DOCUMENT_PROCESSING_URL = config(
    'DOCUMENT_PROCESSING_URL',
    default='http://localhost:8000',
)

SERVICE_API_KEY = config('SERVICE_API_KEY', default='service_api_key')
DOCUMENT_PROCESSING_TIMEOUT_SECONDS = config(
    'DOCUMENT_PROCESSING_TIMEOUT_SECONDS',
    default=300,
    cast=int,
)

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

DOC_COLLECTION_SERVICE_URL = config('DOC_COLLECTION_SERVICE_URL', default='http://localhost:8005')

CHAT_SERVICE_URL = config('CHAT_SERVICE_URL', default='http://localhost:8003')

LLM_SERVICE_URL = config('LLM_SERVICE_URL', default='http://localhost:8001')

SERVICE_HEALTH_CHECK_TIMEOUT_SECONDS = config(
    'SERVICE_HEALTH_CHECK_TIMEOUT_SECONDS',
    default=3,
    cast=int,
)

NEO4J_HTTP_URL = config('NEO4J_HTTP_URL', default='http://neo4j:7474')
NEO4J_HTTP_USER = config('NEO4J_HTTP_USER', default='neo4j')
NEO4J_HTTP_PASSWORD = config('NEO4J_HTTP_PASSWORD', default='aura_password')

RABBITMQ_MGMT_URL = config('RABBITMQ_MGMT_URL', default='http://queue:15672')
RABBITMQ_MGMT_USER = config('RABBITMQ_MGMT_USER', default='aura_root')
RABBITMQ_MGMT_PASSWORD = config('RABBITMQ_MGMT_PASSWORD', default='aura_password')

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

ENVIRONMENT = config('ENVIRONMENT', default='development')

SESSION_COOKIE_AGE = 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
