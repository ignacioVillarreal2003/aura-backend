import jwt
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User


def make_mock_user(**kwargs):
    user = MagicMock(spec=User)
    user.id = kwargs.get("id", 1)
    user.pk = user.id
    user.username = kwargs.get("username", "testuser")
    user.email = kwargs.get("email", "test@example.com")
    user.name = kwargs.get("name", "Test User")
    user.status = kwargs.get("status", "active")
    user.is_deleted = kwargs.get("is_deleted", False)
    user.deleted_at = None
    user.account_non_locked = kwargs.get("account_non_locked", True)
    user.lockout_until = kwargs.get("lockout_until", None)
    user.is_superuser = kwargs.get("is_superuser", False)
    user.tokens_valid_after = kwargs.get("tokens_valid_after", None)
    return user


def make_access_token(user_id=1, expired=False):
    delta = timedelta(hours=1) if not expired else -timedelta(hours=1)
    exp = int((timezone.now() + delta).timestamp())
    payload = {"user_id": user_id, "is_super_admin": False, "exp": exp}
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture
def api_client():
    return APIClient()
