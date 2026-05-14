from .base import *

DATABASES["default"]["TEST"] = {"NAME": DATABASES["default"]["NAME"]}

DEBUG = True
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    }
}

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
}
