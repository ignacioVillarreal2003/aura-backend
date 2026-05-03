import os
import sys

_svc = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "aura-document-collection-service")
)
if _svc not in sys.path:
    sys.path.insert(0, _svc)

from aura_document_collection_service.settings.base import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

MIDDLEWARE = [
    m for m in MIDDLEWARE  # noqa: F405
    if m != "core.authentication.authentication_middleware.AuthenticationMiddleware"
]
