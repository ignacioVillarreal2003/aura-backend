"""
Unit tests for AuthenticatedUser model.
"""
import pytest
from pydantic import ValidationError

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.types import UserId


def _user(**kwargs):
    defaults = {"id": UserId(1), "email": "test@example.com"}
    return AuthenticatedUser(**{**defaults, **kwargs})


class TestHasRole:
    def test_has_role_returns_true_when_present(self):
        user = _user(roles=["ADMIN", "USER"])
        assert user.has_role("ADMIN") is True

    def test_has_role_returns_false_when_absent(self):
        user = _user(roles=["USER"])
        assert user.has_role("ADMIN") is False

    def test_has_role_empty_roles(self):
        assert _user(roles=[]).has_role("USER") is False


class TestHasAnyRole:
    def test_returns_true_when_one_matches(self):
        user = _user(roles=["USER"])
        assert user.has_any_role({"USER", "ADMIN"}) is True

    def test_returns_false_when_none_match(self):
        user = _user(roles=["USER"])
        assert user.has_any_role({"ADMIN", "SUPERADMIN"}) is False

    def test_empty_required_set_returns_false(self):
        assert _user(roles=["USER"]).has_any_role(set()) is False


class TestHasPermission:
    def test_returns_true_when_present(self):
        user = _user(permissions=["GET_DOCUMENT", "LIST_DOCUMENTS"])
        assert user.has_permission("GET_DOCUMENT") is True

    def test_returns_false_when_absent(self):
        user = _user(permissions=["LIST_DOCUMENTS"])
        assert user.has_permission("GET_DOCUMENT") is False

    def test_empty_permissions(self):
        assert _user(permissions=[]).has_permission("GET_DOCUMENT") is False


class TestHasAnyPermission:
    def test_returns_true_when_one_matches(self):
        user = _user(permissions=["GET_DOCUMENT"])
        assert user.has_any_permission({"GET_DOCUMENT", "LIST_DOCUMENTS"}) is True

    def test_returns_false_when_none_match(self):
        user = _user(permissions=["GET_DOCUMENT"])
        assert user.has_any_permission({"INGEST_DOCUMENT"}) is False


class TestHasAllPermissions:
    def test_returns_true_when_all_present(self):
        user = _user(permissions=["GET_DOCUMENT", "LIST_DOCUMENTS"])
        assert user.has_all_permissions({"GET_DOCUMENT", "LIST_DOCUMENTS"}) is True

    def test_returns_false_when_one_missing(self):
        user = _user(permissions=["GET_DOCUMENT"])
        assert user.has_all_permissions({"GET_DOCUMENT", "LIST_DOCUMENTS"}) is False

    def test_empty_required_set_returns_true(self):
        assert _user(permissions=[]).has_all_permissions(set()) is True


class TestImmutability:
    def test_model_is_frozen(self):
        user = _user()
        with pytest.raises(ValidationError):
            user.email = "other@example.com"
