from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIRequestFactory

from apps.accounts.authentication import JWTAuthentication, ServiceKeyAuthentication, ServiceAccount
from tests.conftest import make_mock_user, make_access_token

_factory = APIRequestFactory()


def _make_request(auth_header=None, service_key=None):
    request = _factory.get("/")
    if auth_header:
        request.META["HTTP_AUTHORIZATION"] = auth_header
    if service_key:
        request.META["HTTP_X_SERVICE_API_KEY"] = service_key
    return request


# ---------------------------------------------------------------------------
# TestJWTAuthentication
# ---------------------------------------------------------------------------

class TestJWTAuthentication:

    def test_valid_token_returns_user_and_token(self, mocker):
        user = make_mock_user(id=5)
        mocker.patch("apps.accounts.authentication.authenticate_access_token", return_value=user)
        token = make_access_token(user_id=5)
        request = _make_request(auth_header=f"Bearer {token}")
        backend = JWTAuthentication()
        result = backend.authenticate(request)
        assert result is not None
        assert result[0] == user
        assert result[1] == token

    def test_no_header_returns_none(self):
        request = _make_request()
        backend = JWTAuthentication()
        result = backend.authenticate(request)
        assert result is None

    def test_non_bearer_scheme_returns_none(self):
        request = _make_request(auth_header="Basic dXNlcjpwYXNz")
        backend = JWTAuthentication()
        result = backend.authenticate(request)
        assert result is None

    def test_invalid_token_raises_authentication_failed(self, mocker):
        mocker.patch("apps.accounts.authentication.authenticate_access_token", return_value=None)
        request = _make_request(auth_header="Bearer invalidtoken")
        backend = JWTAuthentication()
        with pytest.raises(AuthenticationFailed):
            backend.authenticate(request)

    def test_expired_token_raises_authentication_failed(self, mocker):
        mocker.patch("apps.accounts.authentication.authenticate_access_token", return_value=None)
        token = make_access_token(expired=True)
        request = _make_request(auth_header=f"Bearer {token}")
        backend = JWTAuthentication()
        with pytest.raises(AuthenticationFailed):
            backend.authenticate(request)

    def test_user_not_found_raises_authentication_failed(self, mocker):
        mocker.patch("apps.accounts.authentication.authenticate_access_token", return_value=None)
        request = _make_request(auth_header="Bearer some.token.here")
        backend = JWTAuthentication()
        with pytest.raises(AuthenticationFailed):
            backend.authenticate(request)

    def test_inactive_user_raises_authentication_failed(self, mocker):
        mocker.patch("apps.accounts.authentication.authenticate_access_token", return_value=None)
        request = _make_request(auth_header="Bearer sometoken")
        backend = JWTAuthentication()
        with pytest.raises(AuthenticationFailed):
            backend.authenticate(request)

    def test_empty_token_after_bearer_returns_none(self):
        request = _make_request(auth_header="Bearer ")
        backend = JWTAuthentication()
        result = backend.authenticate(request)
        assert result is None

    def test_authenticate_header_returns_bearer(self):
        backend = JWTAuthentication()
        request = _make_request()
        assert backend.authenticate_header(request) == "Bearer"


# ---------------------------------------------------------------------------
# TestServiceKeyAuthentication
# ---------------------------------------------------------------------------

class TestServiceKeyAuthentication:

    def test_valid_key_returns_service_account(self, settings):
        settings.SERVICE_API_KEY = "test-service-key-123"
        request = _make_request(service_key="test-service-key-123")
        backend = ServiceKeyAuthentication()
        result = backend.authenticate(request)
        assert result is not None
        assert isinstance(result[0], ServiceAccount)

    def test_invalid_key_raises_authentication_failed(self, settings):
        settings.SERVICE_API_KEY = "correct-key"
        request = _make_request(service_key="wrong-key")
        backend = ServiceKeyAuthentication()
        with pytest.raises(AuthenticationFailed):
            backend.authenticate(request)

    def test_no_header_returns_none(self):
        request = _make_request()
        backend = ServiceKeyAuthentication()
        result = backend.authenticate(request)
        assert result is None

    def test_service_account_is_service_true(self, settings):
        settings.SERVICE_API_KEY = "mykey"
        request = _make_request(service_key="mykey")
        backend = ServiceKeyAuthentication()
        result = backend.authenticate(request)
        assert result[0].is_service is True

    def test_service_account_is_superuser_false(self, settings):
        settings.SERVICE_API_KEY = "mykey"
        request = _make_request(service_key="mykey")
        backend = ServiceKeyAuthentication()
        result = backend.authenticate(request)
        assert result[0].is_superuser is False

    def test_service_account_is_authenticated_true(self, settings):
        settings.SERVICE_API_KEY = "mykey"
        request = _make_request(service_key="mykey")
        backend = ServiceKeyAuthentication()
        result = backend.authenticate(request)
        assert result[0].is_authenticated is True

    def test_empty_key_returns_none(self):
        request = _make_request()
        backend = ServiceKeyAuthentication()
        result = backend.authenticate(request)
        assert result is None

    def test_authenticate_header_returns_header_name(self):
        backend = ServiceKeyAuthentication()
        request = _make_request()
        assert backend.authenticate_header(request) == "X-Service-Api-Key"

    def test_key_is_compared_in_constant_time(self, settings, mocker):
        settings.SERVICE_API_KEY = "secret"
        mock_compare = mocker.patch("apps.accounts.authentication.secrets.compare_digest", return_value=True)
        request = _make_request(service_key="secret")
        backend = ServiceKeyAuthentication()
        backend.authenticate(request)
        mock_compare.assert_called_once()
