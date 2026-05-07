"""
Fixtures compartidas para los tests funcionales del aura-notification-service.

Estrategia:
- Se parchea get_user_from_request para inyectar el usuario sin llamar al auth service.
- Se parchea Notification.objects para evitar acceso real a la BD (managed=False).
- Los objetos Notification se crean con el constructor de Django (sin save()),
  lo que no requiere conexión a BD.
- raise_request_exception=False captura respuestas 500 sin propagar la excepción.
"""

import os
import sys
from unittest.mock import MagicMock, patch

_svc = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "aura-notification-service")
)
if _svc not in sys.path:
    sys.path.insert(0, _svc)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings_test")

import django
from django.test.utils import setup_test_environment

django.setup()
setup_test_environment()

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from notifications.models import Notification

USER_ID = 1
ADMIN_USER_ID = 99
INTERNAL_TOKEN = "dev-notification-internal-token"


def make_notification(id=1, receiver_id=USER_ID, message="Mensaje de prueba",
                       notification_type="admin", status="unread"):
    """Crea una instancia de Notification en memoria (sin guardar en BD)."""
    notif = Notification(
        receiver_id=receiver_id,
        message=message,
        type=notification_type,
        status=status,
        target_scope="individual",
        created_by=ADMIN_USER_ID,
        updated_by=ADMIN_USER_ID,
    )
    notif.id = id
    notif.pk = id
    notif.created_at = timezone.now()
    notif.updated_at = timezone.now()
    notif.save = MagicMock()
    notif.delete = MagicMock()
    return notif


def make_mock_queryset(items=None):
    """Mock de queryset que soporta count(), len() y slicing para el paginador de DRF."""
    items = items or []
    qs = MagicMock()
    qs.count.return_value = len(items)
    qs.__len__ = MagicMock(return_value=len(items))
    qs.__getitem__ = MagicMock(side_effect=lambda idx: items[idx])
    qs.filter.return_value = qs
    qs.first.return_value = items[0] if items else None
    return qs


@pytest.fixture
def client():
    api_client = APIClient()
    api_client.raise_request_exception = False
    return api_client


@pytest.fixture
def mock_get_user():
    """Usuario autenticado estándar (no superadmin)."""
    with patch("notifications.api.views.get_user_from_request") as mock:
        mock.return_value = {"user_id": USER_ID, "is_super_admin": False}
        yield mock


@pytest.fixture
def mock_super_admin():
    """Usuario autenticado con rol superadmin."""
    with patch("notifications.api.views.get_user_from_request") as mock:
        mock.return_value = {"user_id": ADMIN_USER_ID, "is_super_admin": True}
        yield mock


@pytest.fixture
def mock_notification_manager():
    """Parchea Notification.objects para evitar acceso real a la BD."""
    with patch.object(Notification, "objects") as mock_mgr:
        mock_mgr.bulk_create.side_effect = lambda objs, **kwargs: objs
        yield mock_mgr
