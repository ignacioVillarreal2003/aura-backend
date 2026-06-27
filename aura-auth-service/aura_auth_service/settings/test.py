"""Configuracion de tests, con una base de pruebas propia en PostgreSQL."""

from .base import *  # noqa: F401, F403

TEST_RUNNER = 'aura_auth_service.test_runner.AuthDbTestRunner'

REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_THROTTLE_RATES': {
        'login': None,
        'refresh': None,
        'change_password': None,
        'user_lookup': None,
    },
}

CACHES = {  # noqa: F405
    **CACHES,  # noqa: F405
    'permissions': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
    'throttle': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'auth_db',
        'USER': config('DB_USER', default='aura_root'),        # noqa: F405
        'PASSWORD': config('DB_PASSWORD', default='aura_password'),  # noqa: F405
        'HOST': config('DB_HOST', default='localhost'),         # noqa: F405
        'PORT': config('DB_PORT', default='5433'),              # noqa: F405
        'TEST': {
            'NAME': 'test_auth_db',
        },
    },
    'aura_db': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}
