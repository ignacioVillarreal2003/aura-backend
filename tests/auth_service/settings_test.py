import os
import sys

_svc = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "aura-auth-service")
)
if _svc not in sys.path:
    sys.path.insert(0, _svc)
_apps = os.path.join(_svc, "apps")
if _apps not in sys.path:
    sys.path.insert(0, _apps)

# Stub out LDAP dependencies for local test execution on Windows
import types
from unittest.mock import MagicMock

dummy_ldap = types.ModuleType('ldap')
dummy_ldap.SCOPE_SUBTREE = 2
sys.modules['ldap'] = dummy_ldap

sys.modules['django_auth_ldap'] = MagicMock()

class DummyLDAPBackend:
    def authenticate(self, *args, **kwargs):
        pass
    def get_or_build_user(self, *args, **kwargs):
        pass
dummy_backend = types.ModuleType('django_auth_ldap.backend')
dummy_backend.LDAPBackend = DummyLDAPBackend
from django.dispatch import Signal
dummy_backend.populate_user = Signal()
sys.modules['django_auth_ldap.backend'] = dummy_backend

class DummyLDAPSearch:
    def __init__(self, *args, **kwargs):
        pass
dummy_config = types.ModuleType('django_auth_ldap.config')
dummy_config.LDAPSearch = DummyLDAPSearch
sys.modules['django_auth_ldap.config'] = dummy_config

from aura_auth_service.settings.base import *  # noqa: F401, F403

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
    "apps.accounts.apps.AccountsConfig",
    "apps.documents.apps.DocumentsConfig",
]

ROOT_URLCONF = "urls_test"
