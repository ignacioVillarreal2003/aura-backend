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
