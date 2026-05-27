"""
Django settings for authservice project.

Environment-based configuration using python-decouple.
Database: PostgreSQL 17
Python: 3.13
Django: 5.x
"""

from pathlib import Path
from decouple import config, Csv
import os

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

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
    'django_extensions',
    
    # Third-party apps
    'corsheaders',
    'rest_framework',
    'django_filters',
    'drf_spectacular',
    
    # Local apps
    'accounts.apps.AccountsConfig',
    'documents.apps.DocumentsConfig',
    'notifications.apps.NotificationsConfig',
    'chat.apps.ChatConfig',
]

# Local apps whose tables are owned by docker/auth-db/init.sql or docker/aura-db/init.sql.
# Setting to None disables Django migrations entirely for these apps.
_LOCAL_APPS = ['accounts', 'documents', 'notifications', 'chat']
MIGRATION_MODULES = {app: None for app in _LOCAL_APPS}

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'accounts.middleware.elevation_middleware.ElevationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'authservice.urls'

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

WSGI_APPLICATION = 'authservice.wsgi.application'

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
DATABASE_ROUTERS = ['authservice.db_routers.AuraDbRouter']

# CORS Configuration
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://localhost:4200', cast=Csv())

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
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
JWT_SIGNING_KEY = config('JWT_SIGNING_KEY', default=SECRET_KEY)

# ID of the shared admin chat in aura_db used for admin-initiated document uploads.
# Must match the seed row in docker/aura-db/init.sql.
ADMIN_CHAT_ID = config('ADMIN_CHAT_ID', default=12345, cast=int)

# Document Processing Service
DOCUMENT_PROCESSING_URL = config(
    'DOCUMENT_PROCESSING_URL',
    default='http://localhost:8000',
)
DOCUMENT_PROCESSING_SERVICE_API_KEY = config(
    'DOCUMENT_PROCESSING_SERVICE_API_KEY',
    default='service_api_key',
)
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
DOC_COLLECTION_SERVICE_API_KEY = config('DOC_COLLECTION_SERVICE_API_KEY', default='dev-doc-collection-key')

# Logging Configuration
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
            'format': '%(asctime)s %(levelname)s %(name)s %(module)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'debug.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Environment
ENVIRONMENT = config('ENVIRONMENT', default='development')

# Session — 1 hour for admin/superadmin panel
SESSION_COOKIE_AGE = 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Security Settings (for production)
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_SECURITY_POLICY = {
        'default-src': ("'self'",),
    }
