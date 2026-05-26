"""
Unit tests for Authorizer.
"""
import pytest

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import AppException
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.types import UserId

_authorizer = Authorizer()


def _user(permissions: list[str]):
    return AuthenticatedUser(id=UserId(1), email="u@test.com", permissions=permissions)


class TestRequirePermissions:
    def test_passes_with_exact_permissions(self):
        user = _user(["GET_DOCUMENT"])
        _authorizer.require_permissions(user, frozenset({"GET_DOCUMENT"}))

    def test_passes_with_superset_of_permissions(self):
        user = _user(["GET_DOCUMENT", "LIST_DOCUMENTS", "INGEST_DOCUMENT"])
        _authorizer.require_permissions(user, frozenset({"GET_DOCUMENT"}))

    def test_passes_with_empty_required_set(self):
        _authorizer.require_permissions(_user([]), frozenset())

    def test_raises_when_permission_missing(self):
        with pytest.raises(UnauthorizedException):
            _authorizer.require_permissions(_user([]), frozenset({"GET_DOCUMENT"}))

    def test_raises_when_one_of_two_missing(self):
        user = _user(["GET_DOCUMENT"])
        with pytest.raises(UnauthorizedException):
            _authorizer.require_permissions(user, frozenset({"GET_DOCUMENT", "LIST_DOCUMENTS"}))

    def test_exception_has_403_status(self):
        with pytest.raises(UnauthorizedException) as exc_info:
            _authorizer.require_permissions(_user([]), frozenset({"GET_DOCUMENT"}))
        assert exc_info.value.status_code == 403

    def test_exception_is_app_exception(self):
        with pytest.raises(AppException):
            _authorizer.require_permissions(_user([]), frozenset({"GET_DOCUMENT"}))
