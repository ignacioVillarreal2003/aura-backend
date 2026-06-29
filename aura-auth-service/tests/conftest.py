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
    user.force_logout_at = kwargs.get("force_logout_at", None)
    return user


def make_access_token(user_id=1, expired=False):
    delta = timedelta(hours=1) if not expired else -timedelta(hours=1)
    exp = int((timezone.now() + delta).timestamp())
    payload = {"user_id": user_id, "is_super_admin": False, "exp": exp}
    return jwt.encode(payload, settings.JWT_SIGNING_KEY, algorithm=settings.JWT_ALGORITHM)


@pytest.fixture(scope="session")
def django_db_setup(request, django_test_environment, django_db_blocker):
    """Replica AuthDbTestRunner bajo pytest: corre init.sql antes de migrar.

    pytest-django ignora TEST_RUNNER, así que sin esto las tablas managed=False
    de accounts (auth_user, refresh_tokens, role, ...) nunca se crean y el FK de
    django_admin_log a auth_user falla. Intercambiamos la clase de creación por
    AuthDbCreation (que corre init.sql) y dejamos que setup_databases haga el
    resto. keepdb=False fuerza BD fresca porque init.sql usa CREATE TABLE sin
    IF NOT EXISTS.
    """
    from django.db import connections
    from django.test.utils import setup_databases, teardown_databases
    from aura_auth_service.test_runner import AuthDbCreation

    connections["default"].creation.__class__ = AuthDbCreation
    with django_db_blocker.unblock():
        db_cfg = setup_databases(
            verbosity=request.config.option.verbose,
            interactive=False,
            keepdb=False,
        )

    yield

    with django_db_blocker.unblock():
        teardown_databases(db_cfg, verbosity=request.config.option.verbose)


@pytest.fixture
def api_client():
    return APIClient()
