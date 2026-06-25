"""
Fixtures compartidas para los tests funcionales del aura-auth-service.

Estrategia:
- Las vistas tienen authentication_classes=[] y permission_classes=[], por lo que
  no se necesita autenticación ni force_authenticate.
- Se parchean las funciones del servicio para evitar acceso real a la BD.
- raise_request_exception=False permite capturar respuestas 500 sin que
  el test lance la excepción cruda.
"""

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

_svc = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "aura-auth-service")
)
if _svc not in sys.path:
    sys.path.insert(0, _svc)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings_test")

# audit_log.py existe en el __init__ pero no está en el repo.
# Lo stubbeamos en sys.modules antes del setup para que el import no falle.
from unittest.mock import MagicMock
_audit_log_stub = MagicMock()
_audit_log_stub.AuditLog = type("AuditLog", (), {"objects": MagicMock()})
sys.modules.setdefault("accounts.models.audit_log", _audit_log_stub)

# pytest-django handles setup automatically

import pytest
from rest_framework.test import APIClient

USER_ID = 1
VALID_ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test"
VALID_REFRESH_TOKEN = "00000000-0000-0000-0000-000000000001"
TOKEN_RESPONSE = {
    "access_token": VALID_ACCESS_TOKEN,
    "refresh_token": VALID_REFRESH_TOKEN,
    "token_type": "Bearer",
}
USER_INFO = {
    "id": USER_ID,
    "email": "test@test.com",
    "username": "testuser",
    "roles": ["user"],
    "permissions": ["VIEW_COLLECTIONS"],
}


def make_user(id=USER_ID, username="testuser", email="test@test.com"):
    return SimpleNamespace(id=id, pk=id, username=username, email=email)


@pytest.fixture
def client():
    api_client = APIClient()
    api_client.raise_request_exception = False
    return api_client


@pytest.fixture
def mock_auth_service():
    with patch("accounts.api.views.authenticate_user") as mock_auth, \
         patch("accounts.api.views.issue_tokens_for_user") as mock_issue, \
         patch("accounts.api.views.rotate_refresh_token") as mock_rotate, \
         patch("accounts.api.views.revoke_refresh_token") as mock_revoke, \
         patch("accounts.api.views.get_user_info") as mock_user_info, \
         patch("accounts.api.views.log_audit"):
        yield {
            "authenticate_user": mock_auth,
            "issue_tokens_for_user": mock_issue,
            "rotate_refresh_token": mock_rotate,
            "revoke_refresh_token": mock_revoke,
            "get_user_info": mock_user_info,
        }
