import os
import sys

_svc = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "aura-auth-service")
)
if _svc not in sys.path:
    sys.path.insert(0, _svc)

from authservice.settings import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    "aura_db": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

# El admin de Django activa auto-discovery de módulos admin con archivos faltantes.
# Para tests de API no se necesita.
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "accounts.apps.AccountsConfig",
    "documents.apps.DocumentsConfig",
]

ROOT_URLCONF = "urls_test"
