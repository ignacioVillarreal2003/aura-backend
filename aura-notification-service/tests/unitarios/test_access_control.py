"""
Tests unitarios para AccessControl.
Sin DB — lógica pura.
"""
import pytest
from unittest.mock import MagicMock

from core.authorization.access import AccessControl
from core.authentication.authenticated_user import AuthenticatedUser
from core.exceptions.base import InsufficientPermissionsException


def make_user(**kwargs):
    defaults = dict(id=1, email="test@test.com", username="testuser")
    defaults.update(kwargs)
    return AuthenticatedUser(**defaults)


class TestRequirePermissions:
    def test_passes_with_required_permissions(self):
        user = make_user(permissions=("read", "write"))
        AccessControl.require_permissions(user, frozenset({"read"}))

    def test_raises_when_missing_permission(self):
        user = make_user(permissions=("read",))
        with pytest.raises(InsufficientPermissionsException):
            AccessControl.require_permissions(user, frozenset({"read", "admin"}))

    def test_service_user_bypasses_check(self):
        user = make_user(permissions=(), is_service=True)
        AccessControl.require_permissions(user, frozenset({"any.permission"}))

    def test_empty_required_always_passes(self):
        user = make_user(permissions=())
        AccessControl.require_permissions(user, frozenset())

    def test_raises_insufficient_permissions_type(self):
        user = make_user(permissions=())
        with pytest.raises(InsufficientPermissionsException):
            AccessControl.require_permissions(user, frozenset({"needed"}))

    def test_error_code_is_correct(self):
        user = make_user(permissions=())
        try:
            AccessControl.require_permissions(user, frozenset({"needed"}))
        except InsufficientPermissionsException as exc:
            assert exc.error_code == "insufficient_permissions"


class TestRequireSuperAdmin:
    def test_passes_for_superadmin_role(self):
        user = make_user(roles=("superadmin",))
        AccessControl.require_super_admin(user)

    def test_raises_for_non_superadmin(self):
        user = make_user(roles=("viewer",))
        with pytest.raises(InsufficientPermissionsException):
            AccessControl.require_super_admin(user)

    def test_error_code_is_superadmin_required(self):
        user = make_user(roles=("viewer",))
        try:
            AccessControl.require_super_admin(user)
        except InsufficientPermissionsException as exc:
            assert exc.error_code == "superadmin_required"

    def test_service_user_can_bypass(self):
        user = make_user(is_service=True)
        AccessControl.require_permissions(user, frozenset({"superadmin_action"}))
