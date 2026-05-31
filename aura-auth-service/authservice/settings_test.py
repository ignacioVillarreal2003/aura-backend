"""Test settings — PostgreSQL with a dedicated test DB."""

from authservice.settings import *  # noqa: F401, F403

TEST_RUNNER = 'authservice.test_runner.AuthDbTestRunner'

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
