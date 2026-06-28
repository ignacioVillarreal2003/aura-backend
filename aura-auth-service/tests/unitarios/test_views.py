import uuid
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from tests.conftest import make_mock_user, make_access_token

LOGIN_URL = "/auth/login"
REFRESH_URL = "/auth/refresh"
LOGOUT_URL = "/auth/logout"
VALIDATE_URL = "/auth/validate"
LOOKUP_URL = "/auth/users/lookup"
BY_IDS_URL = "/auth/users/by-ids"
CHANGE_PASSWORD_URL = "/auth/change-password"

_VIEWS = "apps.accounts.api.views"

_FAKE_TOKENS = {
    "access_token": "fake.access.token",
    "refresh_token": str(uuid.uuid4()),
    "token_type": "Bearer",
}


# ---------------------------------------------------------------------------
# TestLoginView
# ---------------------------------------------------------------------------

class TestLoginView:

    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.issue_tokens_for_user", return_value=_FAKE_TOKENS)
    @patch(f"{_VIEWS}.authenticate_user")
    def test_valid_credentials_return_200(self, mock_auth, mock_issue, mock_log, api_client):
        mock_auth.return_value = make_mock_user()
        resp = api_client.post(LOGIN_URL, {"username": "testuser", "password": "pass"}, format="json")
        assert resp.status_code == 200
        assert "access_token" in resp.data
        assert "refresh_token" in resp.data

    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.authenticate_user", return_value=None)
    def test_invalid_credentials_return_401(self, mock_auth, mock_log, api_client):
        resp = api_client.post(LOGIN_URL, {"username": "bad", "password": "wrong"}, format="json")
        assert resp.status_code == 401
        assert resp.data["detail"] == "Invalid credentials."

    def test_missing_fields_return_400(self, api_client):
        resp = api_client.post(LOGIN_URL, {"username": "only"}, format="json")
        assert resp.status_code == 400

    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.authenticate_user", return_value=None)
    def test_inactive_user_returns_401(self, mock_auth, mock_log, api_client):
        resp = api_client.post(LOGIN_URL, {"username": "inactive", "password": "pass"}, format="json")
        assert resp.status_code == 401

    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.authenticate_user", return_value=None)
    def test_deleted_user_returns_401(self, mock_auth, mock_log, api_client):
        resp = api_client.post(LOGIN_URL, {"username": "deleted", "password": "pass"}, format="json")
        assert resp.status_code == 401

    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.authenticate_user", return_value=None)
    def test_locked_account_returns_401(self, mock_auth, mock_log, api_client):
        resp = api_client.post(LOGIN_URL, {"username": "locked", "password": "pass"}, format="json")
        assert resp.status_code == 401

    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.issue_tokens_for_user", return_value=_FAKE_TOKENS)
    @patch(f"{_VIEWS}.authenticate_user")
    def test_successful_login_calls_log_audit(self, mock_auth, mock_issue, mock_log, api_client):
        mock_auth.return_value = make_mock_user()
        api_client.post(LOGIN_URL, {"username": "testuser", "password": "pass"}, format="json")
        mock_log.assert_called()

    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.authenticate_user", return_value=None)
    def test_failed_login_calls_log_audit(self, mock_auth, mock_log, api_client):
        api_client.post(LOGIN_URL, {"username": "x", "password": "y"}, format="json")
        mock_log.assert_called_once()

    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.issue_tokens_for_user", return_value=_FAKE_TOKENS)
    @patch(f"{_VIEWS}.authenticate_user")
    def test_response_has_token_type(self, mock_auth, mock_issue, mock_log, api_client):
        mock_auth.return_value = make_mock_user()
        resp = api_client.post(LOGIN_URL, {"username": "testuser", "password": "pass"}, format="json")
        assert resp.data["token_type"] == "Bearer"

    @patch(f"{_VIEWS}.emit_event_async")
    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.issue_tokens_for_user", return_value=_FAKE_TOKENS)
    @patch(f"{_VIEWS}.authenticate_user")
    @patch(f"{_VIEWS}._is_new_device_login", return_value=True)
    def test_new_device_login_calls_emit_event(self, mock_new_dev, mock_auth, mock_issue, mock_log, mock_emit, api_client):
        mock_auth.return_value = make_mock_user()
        api_client.post(LOGIN_URL, {"username": "testuser", "password": "pass"}, format="json")
        mock_emit.assert_called_once()

    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.issue_tokens_for_user", return_value=_FAKE_TOKENS)
    @patch(f"{_VIEWS}.authenticate_user")
    def test_response_has_three_token_fields(self, mock_auth, mock_issue, mock_log, api_client):
        mock_auth.return_value = make_mock_user()
        resp = api_client.post(LOGIN_URL, {"username": "testuser", "password": "pass"}, format="json")
        assert "access_token" in resp.data
        assert "refresh_token" in resp.data
        assert "token_type" in resp.data

    def test_empty_body_returns_400(self, api_client):
        resp = api_client.post(LOGIN_URL, {}, format="json")
        assert resp.status_code == 400

    def test_missing_password_returns_400(self, api_client):
        resp = api_client.post(LOGIN_URL, {"username": "user"}, format="json")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# TestRefreshView
# ---------------------------------------------------------------------------

class TestRefreshView:

    def _valid_token(self):
        return str(uuid.uuid4())

    @patch(f"{_VIEWS}.rotate_refresh_token", return_value=_FAKE_TOKENS)
    def test_valid_token_returns_200(self, mock_rotate, api_client):
        resp = api_client.post(REFRESH_URL, {"refresh_token": self._valid_token()}, format="json")
        assert resp.status_code == 200
        assert "access_token" in resp.data

    @patch(f"{_VIEWS}.rotate_refresh_token", return_value=None)
    def test_invalid_token_returns_401(self, mock_rotate, api_client):
        resp = api_client.post(REFRESH_URL, {"refresh_token": self._valid_token()}, format="json")
        assert resp.status_code == 401
        assert resp.data["detail"] == "Invalid refresh token."

    @patch(f"{_VIEWS}.rotate_refresh_token", return_value=None)
    def test_expired_token_returns_401(self, mock_rotate, api_client):
        resp = api_client.post(REFRESH_URL, {"refresh_token": self._valid_token()}, format="json")
        assert resp.status_code == 401

    def test_missing_refresh_token_returns_400(self, api_client):
        resp = api_client.post(REFRESH_URL, {}, format="json")
        assert resp.status_code == 400

    def test_malformed_uuid_returns_400(self, api_client):
        resp = api_client.post(REFRESH_URL, {"refresh_token": "not-a-uuid"}, format="json")
        assert resp.status_code == 400

    @patch(f"{_VIEWS}.rotate_refresh_token", return_value=_FAKE_TOKENS)
    def test_response_has_token_type(self, mock_rotate, api_client):
        resp = api_client.post(REFRESH_URL, {"refresh_token": self._valid_token()}, format="json")
        assert resp.data["token_type"] == "Bearer"

    @patch(f"{_VIEWS}.rotate_refresh_token", return_value=_FAKE_TOKENS)
    def test_response_has_three_fields(self, mock_rotate, api_client):
        resp = api_client.post(REFRESH_URL, {"refresh_token": self._valid_token()}, format="json")
        assert "access_token" in resp.data
        assert "refresh_token" in resp.data
        assert "token_type" in resp.data

    @patch(f"{_VIEWS}.rotate_refresh_token", return_value=_FAKE_TOKENS)
    def test_passes_token_to_service(self, mock_rotate, api_client):
        token = self._valid_token()
        api_client.post(REFRESH_URL, {"refresh_token": token}, format="json")
        mock_rotate.assert_called_once()


# ---------------------------------------------------------------------------
# TestLogoutView
# ---------------------------------------------------------------------------

class TestLogoutView:

    def _valid_token(self):
        return str(uuid.uuid4())

    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.revoke_refresh_token", return_value=True)
    def test_valid_token_returns_200(self, mock_revoke, mock_log, api_client):
        resp = api_client.post(LOGOUT_URL, {"refresh_token": self._valid_token()}, format="json")
        assert resp.status_code == 200
        assert resp.data["detail"] == "Logged out."

    @patch(f"{_VIEWS}.revoke_refresh_token", return_value=False)
    def test_invalid_token_returns_401(self, mock_revoke, api_client):
        resp = api_client.post(LOGOUT_URL, {"refresh_token": self._valid_token()}, format="json")
        assert resp.status_code == 401
        assert resp.data["detail"] == "Invalid refresh token."

    def test_missing_token_returns_400(self, api_client):
        resp = api_client.post(LOGOUT_URL, {}, format="json")
        assert resp.status_code == 400

    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.revoke_refresh_token", return_value=True)
    def test_successful_logout_calls_log_audit(self, mock_revoke, mock_log, api_client):
        api_client.post(LOGOUT_URL, {"refresh_token": self._valid_token()}, format="json")
        mock_log.assert_called_once()

    def test_empty_token_string_returns_400(self, api_client):
        resp = api_client.post(LOGOUT_URL, {"refresh_token": ""}, format="json")
        assert resp.status_code == 400

    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.revoke_refresh_token", return_value=True)
    def test_detail_message_on_success(self, mock_revoke, mock_log, api_client):
        resp = api_client.post(LOGOUT_URL, {"refresh_token": self._valid_token()}, format="json")
        assert resp.data["detail"] == "Logged out."


# ---------------------------------------------------------------------------
# TestValidateView
# ---------------------------------------------------------------------------

class TestValidateView:

    _valid_user_info = {
        "id": 1,
        "email": "user@example.com",
        "username": "testuser",
        "name": "Test User",
        "roles": ["admin"],
        "permissions": ["USER_READ"],
    }

    @patch(f"{_VIEWS}.get_user_info")
    def test_valid_token_returns_200(self, mock_info, api_client):
        mock_info.return_value = self._valid_user_info
        resp = api_client.get(VALIDATE_URL, HTTP_AUTHORIZATION="Bearer validtoken")
        assert resp.status_code == 200
        assert resp.data["id"] == 1
        assert resp.data["username"] == "testuser"

    @patch(f"{_VIEWS}.get_user_info", return_value=None)
    def test_invalid_token_returns_401(self, mock_info, api_client):
        resp = api_client.get(VALIDATE_URL, HTTP_AUTHORIZATION="Bearer invalidtoken")
        assert resp.status_code == 401
        assert resp.data["detail"] == "Invalid or expired token."

    def test_missing_authorization_header_returns_401(self, api_client):
        resp = api_client.get(VALIDATE_URL)
        assert resp.status_code == 401
        assert resp.data["detail"] == "Authorization header missing or invalid."

    def test_non_bearer_scheme_returns_401(self, api_client):
        resp = api_client.get(VALIDATE_URL, HTTP_AUTHORIZATION="Basic dXNlcjpwYXNz")
        assert resp.status_code == 401

    @patch(f"{_VIEWS}.get_user_info")
    def test_response_includes_roles_and_permissions(self, mock_info, api_client):
        mock_info.return_value = self._valid_user_info
        resp = api_client.get(VALIDATE_URL, HTTP_AUTHORIZATION="Bearer validtoken")
        assert "roles" in resp.data
        assert "permissions" in resp.data

    @patch(f"{_VIEWS}.get_user_info")
    def test_response_includes_all_user_fields(self, mock_info, api_client):
        mock_info.return_value = self._valid_user_info
        resp = api_client.get(VALIDATE_URL, HTTP_AUTHORIZATION="Bearer validtoken")
        for field in ("id", "email", "username", "name", "roles", "permissions"):
            assert field in resp.data

    def test_post_method_not_allowed(self, api_client):
        resp = api_client.post(VALIDATE_URL, {}, format="json")
        assert resp.status_code == 405


# ---------------------------------------------------------------------------
# TestChangePasswordView
# ---------------------------------------------------------------------------

class TestChangePasswordView:

    @patch(f"{_VIEWS}.emit_event_async")
    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.revoke_all_sessions")
    def test_change_password_returns_200(self, mock_revoke, mock_log, mock_emit, api_client, mocker):
        user = make_mock_user()
        user.check_password.return_value = True
        mocker.patch("apps.accounts.authentication.JWTAuthentication.authenticate", return_value=(user, None))
        resp = api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "oldpass", "new_password": "newStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION="Bearer sometoken",
        )
        assert resp.status_code == 200

    def test_change_password_unauthenticated_returns_401(self, api_client):
        resp = api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "old", "new_password": "new"},
            format="json",
        )
        assert resp.status_code == 401

    def test_change_password_missing_fields_returns_400(self, api_client, mocker):
        user = make_mock_user()
        mocker.patch("apps.accounts.authentication.JWTAuthentication.authenticate", return_value=(user, None))
        resp = api_client.post(
            CHANGE_PASSWORD_URL, {}, format="json", HTTP_AUTHORIZATION="Bearer sometoken"
        )
        assert resp.status_code == 400

    def test_change_password_missing_current_returns_400(self, api_client, mocker):
        user = make_mock_user()
        mocker.patch("apps.accounts.authentication.JWTAuthentication.authenticate", return_value=(user, None))
        resp = api_client.post(
            CHANGE_PASSWORD_URL,
            {"new_password": "NewPass1!"},
            format="json",
            HTTP_AUTHORIZATION="Bearer sometoken",
        )
        assert resp.status_code == 400

    def test_change_password_missing_new_returns_400(self, api_client, mocker):
        user = make_mock_user()
        mocker.patch("apps.accounts.authentication.JWTAuthentication.authenticate", return_value=(user, None))
        resp = api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "OldPass1!"},
            format="json",
            HTTP_AUTHORIZATION="Bearer sometoken",
        )
        assert resp.status_code == 400

    @patch(f"{_VIEWS}.revoke_all_sessions")
    @patch(f"{_VIEWS}.emit_event_async")
    @patch(f"{_VIEWS}.log_audit")
    def test_wrong_current_password_returns_400(self, mock_log, mock_emit, mock_revoke, api_client, mocker):
        user = make_mock_user()
        user.check_password.return_value = False
        mocker.patch("apps.accounts.authentication.JWTAuthentication.authenticate", return_value=(user, None))
        resp = api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "wrongold", "new_password": "NewStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION="Bearer sometoken",
        )
        assert resp.status_code == 400

    @patch(f"{_VIEWS}.emit_event_async")
    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.revoke_all_sessions")
    def test_success_calls_revoke_all_sessions(self, mock_revoke, mock_log, mock_emit, api_client, mocker):
        user = make_mock_user()
        user.check_password.return_value = True
        mocker.patch("apps.accounts.authentication.JWTAuthentication.authenticate", return_value=(user, None))
        api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "oldpass", "new_password": "NewStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION="Bearer sometoken",
        )
        mock_revoke.assert_called_once_with(user)

    @patch(f"{_VIEWS}.emit_event_async")
    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.revoke_all_sessions")
    def test_success_calls_emit_event_async(self, mock_revoke, mock_log, mock_emit, api_client, mocker):
        user = make_mock_user()
        user.check_password.return_value = True
        mocker.patch("apps.accounts.authentication.JWTAuthentication.authenticate", return_value=(user, None))
        api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "oldpass", "new_password": "NewStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION="Bearer sometoken",
        )
        mock_emit.assert_called_once()

    @patch(f"{_VIEWS}.emit_event_async")
    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.revoke_all_sessions")
    def test_success_calls_log_audit(self, mock_revoke, mock_log, mock_emit, api_client, mocker):
        user = make_mock_user()
        user.check_password.return_value = True
        mocker.patch("apps.accounts.authentication.JWTAuthentication.authenticate", return_value=(user, None))
        api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "oldpass", "new_password": "NewStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION="Bearer sometoken",
        )
        mock_log.assert_called_once()

    @patch(f"{_VIEWS}.emit_event_async")
    @patch(f"{_VIEWS}.log_audit")
    @patch(f"{_VIEWS}.revoke_all_sessions")
    def test_success_response_has_detail(self, mock_revoke, mock_log, mock_emit, api_client, mocker):
        user = make_mock_user()
        user.check_password.return_value = True
        mocker.patch("apps.accounts.authentication.JWTAuthentication.authenticate", return_value=(user, None))
        resp = api_client.post(
            CHANGE_PASSWORD_URL,
            {"current_password": "oldpass", "new_password": "NewStrongPass1!"},
            format="json",
            HTTP_AUTHORIZATION="Bearer sometoken",
        )
        assert "detail" in resp.data


# ---------------------------------------------------------------------------
# TestUserLookupViewUnit
# ---------------------------------------------------------------------------

class TestUserLookupViewUnit:

    def test_missing_auth_returns_401(self, api_client):
        resp = api_client.get(LOOKUP_URL + "?q=john")
        assert resp.status_code == 401

    def test_missing_q_returns_400(self, api_client, mocker):
        user = make_mock_user()
        type(user).is_authenticated = PropertyMock(return_value=True)
        type(user).is_superuser = PropertyMock(return_value=True)
        mocker.patch("apps.accounts.api.permissions.IsServiceOrUserViewer.has_permission", return_value=True)
        mocker.patch("apps.accounts.authentication.JWTAuthentication.authenticate", return_value=(user, None))
        resp = api_client.get(LOOKUP_URL, HTTP_AUTHORIZATION="Bearer token")
        assert resp.status_code == 400

    def test_service_key_can_lookup(self, api_client, mocker):
        from django.conf import settings
        mocker.patch("apps.accounts.models.User.objects.filter").return_value.filter.return_value = []
        resp = api_client.get(
            LOOKUP_URL + "?q=z",
            HTTP_X_SERVICE_API_KEY=settings.SERVICE_API_KEY,
        )
        assert resp.status_code == 200

    def test_service_key_response_has_count(self, api_client, mocker):
        from django.conf import settings
        mocker.patch("apps.accounts.models.User.objects.filter").return_value.filter.return_value = []
        resp = api_client.get(
            LOOKUP_URL + "?q=nobody",
            HTTP_X_SERVICE_API_KEY=settings.SERVICE_API_KEY,
        )
        assert "count" in resp.data

    def test_service_key_response_has_results(self, api_client, mocker):
        from django.conf import settings
        mocker.patch("apps.accounts.models.User.objects.filter").return_value.filter.return_value = []
        resp = api_client.get(
            LOOKUP_URL + "?q=nobody",
            HTTP_X_SERVICE_API_KEY=settings.SERVICE_API_KEY,
        )
        assert "results" in resp.data

    def test_regular_user_without_permission_returns_403(self, api_client, mocker):
        user = make_mock_user()
        type(user).is_authenticated = PropertyMock(return_value=True)
        mocker.patch("apps.accounts.authentication.JWTAuthentication.authenticate", return_value=(user, None))
        mocker.patch("apps.accounts.api.permissions.IsServiceOrUserViewer.has_permission", return_value=False)
        resp = api_client.get(LOOKUP_URL + "?q=john", HTTP_AUTHORIZATION="Bearer token")
        assert resp.status_code == 403

    def test_empty_q_returns_400(self, api_client, mocker):
        from django.conf import settings
        resp = api_client.get(
            LOOKUP_URL + "?q=",
            HTTP_X_SERVICE_API_KEY=settings.SERVICE_API_KEY,
        )
        assert resp.status_code == 400

    def test_no_match_returns_empty_results(self, api_client, mocker):
        from django.conf import settings
        mocker.patch("apps.accounts.models.User.objects.filter").return_value.filter.return_value = []
        resp = api_client.get(
            LOOKUP_URL + "?q=xyzzzznobodymatch",
            HTTP_X_SERVICE_API_KEY=settings.SERVICE_API_KEY,
        )
        assert resp.status_code == 200
        assert resp.data["results"] == []


# ---------------------------------------------------------------------------
# TestUsersByIdsViewUnit
# ---------------------------------------------------------------------------

class TestUsersByIdsViewUnit:

    def test_missing_ids_returns_400(self, api_client, mocker):
        from django.conf import settings
        resp = api_client.get(
            BY_IDS_URL,
            HTTP_X_SERVICE_API_KEY=settings.SERVICE_API_KEY,
        )
        assert resp.status_code == 400

    def test_invalid_ids_returns_400(self, api_client, mocker):
        from django.conf import settings
        resp = api_client.get(
            BY_IDS_URL + "?ids=abc,def",
            HTTP_X_SERVICE_API_KEY=settings.SERVICE_API_KEY,
        )
        assert resp.status_code == 400

    def test_missing_auth_returns_401(self, api_client):
        resp = api_client.get(BY_IDS_URL + "?ids=1")
        assert resp.status_code == 401

    def test_service_key_includes_email(self, api_client, mocker):
        from django.conf import settings
        mock_user = MagicMock()
        mock_user.id = 99
        mock_user.username = "mockuser"
        mock_user.name = "Mock User"
        mock_user.email = "mock@example.com"
        mocker.patch("apps.accounts.models.User.objects.filter", return_value=[mock_user])
        resp = api_client.get(
            BY_IDS_URL + "?ids=99",
            HTTP_X_SERVICE_API_KEY=settings.SERVICE_API_KEY,
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["email"] == "mock@example.com"

    def test_nonexistent_ids_return_empty(self, api_client, mocker):
        from django.conf import settings
        mocker.patch("apps.accounts.models.User.objects.filter", return_value=[])
        resp = api_client.get(
            BY_IDS_URL + "?ids=999999",
            HTTP_X_SERVICE_API_KEY=settings.SERVICE_API_KEY,
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 0
        assert resp.data["results"] == []

    def test_empty_ids_param_returns_400(self, api_client, mocker):
        from django.conf import settings
        resp = api_client.get(
            BY_IDS_URL + "?ids=",
            HTTP_X_SERVICE_API_KEY=settings.SERVICE_API_KEY,
        )
        assert resp.status_code == 400

    def test_response_has_count_and_results(self, api_client, mocker):
        from django.conf import settings
        mocker.patch("apps.accounts.models.User.objects.filter", return_value=[])
        resp = api_client.get(
            BY_IDS_URL + "?ids=1",
            HTTP_X_SERVICE_API_KEY=settings.SERVICE_API_KEY,
        )
        assert "count" in resp.data
        assert "results" in resp.data
