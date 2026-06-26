"""Test settings — PostgreSQL with a dedicated test DB."""

from .base import *  # noqa: F401, F403

TEST_RUNNER = 'aura_auth_service.test_runner.AuthDbTestRunner'

# Disable throttling under tests: the throttle state lives in LocMemCache and
# would otherwise leak across test methods (in-process), causing flaky 429s.
REST_FRAMEWORK = {  # noqa: F405
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_THROTTLE_RATES': {
        'login': None,
        'refresh': None,
        'change_password': None,
        'user_lookup': None,
    },
}

# Keep the permissions and throttle caches in-process during tests (no Redis
# dependency). Throttling is disabled above, so the throttle cache is never hit
# anyway, but this removes Redis from the test path entirely.
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
            'NAME': 'test_auth_db',  # fixed name, no test_ prefix doubling
        },
    },
    'aura_db': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}
