"""
Unit tests for Authorizer.require_permissions.
"""
import pytest
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.authorization_exceptions import UnauthorizedException
from app.domain.authentication.authenticated_user import AuthenticatedUser


def _user(permissions: list[str]) -> AuthenticatedUser:
    return AuthenticatedUser(id=1, email="u@test.com", permissions=permissions)


authorizer = Authorizer()


class TestRequirePermissions:
    def test_passes_when_user_has_required_permission(self):
        user = _user(["LLM_DOCUMENT_QUESTION"])
        authorizer.require_permissions(user, frozenset({"LLM_DOCUMENT_QUESTION"}))

    def test_passes_when_user_has_all_required_permissions(self):
        user = _user(["LLM_DOCUMENT_QUESTION", "LLM_DOCUMENT_CLASSIFY"])
        authorizer.require_permissions(user, frozenset({"LLM_DOCUMENT_QUESTION", "LLM_DOCUMENT_CLASSIFY"}))

    def test_passes_when_user_has_superset_of_required_permissions(self):
        user = _user(["LLM_DOCUMENT_QUESTION", "LLM_AGENT", "LLM_DOCUMENT_CLASSIFY"])
        authorizer.require_permissions(user, frozenset({"LLM_DOCUMENT_QUESTION"}))

    def test_empty_required_set_always_passes(self):
        user = _user([])
        authorizer.require_permissions(user, frozenset())

    def test_raises_when_user_has_no_permissions(self):
        user = _user([])
        with pytest.raises(UnauthorizedException):
            authorizer.require_permissions(user, frozenset({"LLM_DOCUMENT_QUESTION"}))

    def test_raises_when_user_missing_one_required_permission(self):
        user = _user(["LLM_DOCUMENT_QUESTION"])
        with pytest.raises(UnauthorizedException):
            authorizer.require_permissions(user, frozenset({"LLM_DOCUMENT_QUESTION", "LLM_AGENT"}))

    def test_raises_when_user_has_wrong_permissions(self):
        user = _user(["LLM_AGENT"])
        with pytest.raises(UnauthorizedException):
            authorizer.require_permissions(user, frozenset({"LLM_DOCUMENT_QUESTION"}))

    def test_exception_is_subclass_of_app_exception(self):
        from app.application.exceptions.app_exception import AppException
        user = _user([])
        with pytest.raises(AppException):
            authorizer.require_permissions(user, frozenset({"LLM_DOCUMENT_QUESTION"}))

    def test_unauthorized_exception_has_403_status(self):
        user = _user([])
        with pytest.raises(UnauthorizedException) as exc_info:
            authorizer.require_permissions(user, frozenset({"LLM_DOCUMENT_QUESTION"}))
        assert exc_info.value.status_code == 403
