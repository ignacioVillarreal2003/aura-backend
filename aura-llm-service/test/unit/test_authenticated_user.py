"""
Unit tests for AuthenticatedUser domain model.
"""
import pytest
from pydantic import ValidationError

from app.domain.authentication.authenticated_user import AuthenticatedUser


def _user(**kwargs) -> AuthenticatedUser:
    defaults = dict(id=1, email="user@test.com", roles=[], permissions=[])
    defaults.update(kwargs)
    return AuthenticatedUser(**defaults)


class TestHasRole:
    def test_returns_true_when_role_present(self):
        user = _user(roles=["admin"])
        assert user.has_role("admin") is True

    def test_returns_false_when_role_absent(self):
        user = _user(roles=["reader"])
        assert user.has_role("admin") is False

    def test_empty_roles_always_false(self):
        user = _user(roles=[])
        assert user.has_role("admin") is False


class TestHasAnyRole:
    def test_returns_true_when_one_matches(self):
        user = _user(roles=["editor"])
        assert user.has_any_role({"admin", "editor"}) is True

    def test_returns_false_when_none_match(self):
        user = _user(roles=["reader"])
        assert user.has_any_role({"admin", "editor"}) is False

    def test_empty_set_returns_false(self):
        user = _user(roles=["admin"])
        assert user.has_any_role(set()) is False


class TestHasPermission:
    def test_returns_true_when_permission_present(self):
        user = _user(permissions=["LLM_DOCUMENT_QUESTION"])
        assert user.has_permission("LLM_DOCUMENT_QUESTION") is True

    def test_returns_false_when_permission_absent(self):
        user = _user(permissions=["LLM_DOCUMENT_QUESTION"])
        assert user.has_permission("LLM_AGENT") is False

    def test_empty_permissions_always_false(self):
        user = _user(permissions=[])
        assert user.has_permission("LLM_DOCUMENT_QUESTION") is False


class TestHasAnyPermission:
    def test_returns_true_when_at_least_one_matches(self):
        user = _user(permissions=["LLM_DOCUMENT_CLASSIFY"])
        assert user.has_any_permission({"LLM_DOCUMENT_QUESTION", "LLM_DOCUMENT_CLASSIFY"}) is True

    def test_returns_false_when_none_match(self):
        user = _user(permissions=["LLM_AGENT"])
        assert user.has_any_permission({"LLM_DOCUMENT_QUESTION", "LLM_DOCUMENT_CLASSIFY"}) is False


class TestHasAllPermissions:
    def test_returns_true_when_all_present(self):
        user = _user(permissions=["LLM_AGENT", "LLM_DOCUMENT_QUESTION"])
        assert user.has_all_permissions({"LLM_AGENT", "LLM_DOCUMENT_QUESTION"}) is True

    def test_returns_false_when_one_missing(self):
        user = _user(permissions=["LLM_AGENT"])
        assert user.has_all_permissions({"LLM_AGENT", "LLM_DOCUMENT_QUESTION"}) is False

    def test_empty_required_set_always_returns_true(self):
        user = _user(permissions=[])
        assert user.has_all_permissions(set()) is True

    def test_superset_of_permissions_returns_true(self):
        user = _user(permissions=["LLM_AGENT", "LLM_DOCUMENT_QUESTION", "LLM_DOCUMENT_CLASSIFY"])
        assert user.has_all_permissions({"LLM_AGENT"}) is True


class TestImmutability:
    def test_model_is_frozen(self):
        user = _user(permissions=["LLM_AGENT"])
        with pytest.raises(ValidationError):
            user.id = 99
