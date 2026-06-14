"""
Tests for user preference endpoints:
  GET /PUT /api/v1/me/notification-preferences/
"""
import pytest
from unittest.mock import patch

from core.authorization.permissions import (
    NOTIFICATION_PREFERENCES_GLOBAL_GET,
    NOTIFICATION_PREFERENCES_GLOBAL_PUT,
)

_PREFS_SVC = "apps.notification.api.views.preference_views.preference_service"


class TestGlobalPreferenceGetView:
    URL = "/api/v1/me/notification-preferences/"

    def test_returns_401_without_auth(self, api_client):
        assert api_client.get(self.URL).status_code == 401

    def test_returns_403_when_permission_missing(self, api_client, auth_headers):
        response = api_client.get(self.URL, **auth_headers(permissions=["WRONG_PERM"]))
        assert response.status_code == 403

    def test_returns_user_preferences(self, api_client, auth_headers, make_preference):
        prefs = make_preference(inapp_enabled=True, email_enabled=False, mute_until=None)
        with patch(_PREFS_SVC) as svc:
            svc.get_global.return_value = prefs
            response = api_client.get(
                self.URL,
                **auth_headers(permissions=[NOTIFICATION_PREFERENCES_GLOBAL_GET]),
            )

        assert response.status_code == 200
        assert response.data["inapp_enabled"] is True
        assert response.data["email_enabled"] is False
        assert response.data["mute_until"] is None

    def test_returns_defaults_when_user_has_no_saved_preferences(self, api_client, auth_headers, make_preference):
        defaults = make_preference(inapp_enabled=True, email_enabled=True, mute_until=None)
        with patch(_PREFS_SVC) as svc:
            svc.get_global.return_value = defaults
            response = api_client.get(
                self.URL,
                **auth_headers(user_id=99, permissions=[NOTIFICATION_PREFERENCES_GLOBAL_GET]),
            )

        assert response.status_code == 200
        assert response.data["inapp_enabled"] is True
        assert response.data["email_enabled"] is True
        svc.get_global.assert_called_once_with(99)


class TestGlobalPreferencePutView:
    URL = "/api/v1/me/notification-preferences/"

    def test_returns_401_without_auth(self, api_client):
        assert api_client.put(self.URL, {}, format="json").status_code == 401

    def test_returns_403_when_permission_missing(self, api_client, auth_headers):
        response = api_client.put(
            self.URL, {"email_enabled": False}, format="json",
            **auth_headers(permissions=["WRONG_PERM"]),
        )
        assert response.status_code == 403

    def test_disables_email_globally(self, api_client, auth_headers, make_preference):
        updated = make_preference(email_enabled=False)
        with patch(_PREFS_SVC) as svc:
            svc.upsert_global.return_value = updated
            response = api_client.put(
                self.URL, {"email_enabled": False}, format="json",
                **auth_headers(user_id=42, permissions=[NOTIFICATION_PREFERENCES_GLOBAL_PUT]),
            )

        assert response.status_code == 200
        assert response.data["email_enabled"] is False
        call_kwargs = svc.upsert_global.call_args[1]
        assert call_kwargs["email_enabled"] is False
        assert call_kwargs["user_id"] == 42

    def test_disables_inapp_globally(self, api_client, auth_headers, make_preference):
        updated = make_preference(inapp_enabled=False)
        with patch(_PREFS_SVC) as svc:
            svc.upsert_global.return_value = updated
            response = api_client.put(
                self.URL, {"inapp_enabled": False}, format="json",
                **auth_headers(permissions=[NOTIFICATION_PREFERENCES_GLOBAL_PUT]),
            )

        assert response.status_code == 200
        assert response.data["inapp_enabled"] is False

    def test_sets_mute_until_to_future_datetime(self, api_client, auth_headers, make_preference):
        from datetime import datetime, timezone
        future = datetime(2099, 12, 31, 23, 59, tzinfo=timezone.utc)
        updated = make_preference(mute_until=future)
        with patch(_PREFS_SVC) as svc:
            svc.upsert_global.return_value = updated
            response = api_client.put(
                self.URL,
                {"mute_until": "2099-12-31T23:59:00Z"},
                format="json",
                **auth_headers(permissions=[NOTIFICATION_PREFERENCES_GLOBAL_PUT]),
            )

        assert response.status_code == 200
        assert response.data["mute_until"] is not None

    def test_clears_active_mute_when_null_sent(self, api_client, auth_headers, make_preference):
        updated = make_preference(mute_until=None)
        with patch(_PREFS_SVC) as svc:
            svc.upsert_global.return_value = updated
            response = api_client.put(
                self.URL, {"mute_until": None}, format="json",
                **auth_headers(permissions=[NOTIFICATION_PREFERENCES_GLOBAL_PUT]),
            )

        assert response.status_code == 200
        assert response.data["mute_until"] is None
        call_kwargs = svc.upsert_global.call_args[1]
        assert call_kwargs["clear_mute"] is True

    def test_mute_until_in_the_past_returns_400(self, api_client, auth_headers):
        with patch(_PREFS_SVC):
            response = api_client.put(
                self.URL,
                {"mute_until": "2000-01-01T00:00:00Z"},
                format="json",
                **auth_headers(permissions=[NOTIFICATION_PREFERENCES_GLOBAL_PUT]),
            )

        assert response.status_code == 400
        assert "mute_until" in str(response.data)

    def test_empty_body_is_a_valid_no_op(self, api_client, auth_headers, make_preference):
        prefs = make_preference()
        with patch(_PREFS_SVC) as svc:
            svc.upsert_global.return_value = prefs
            response = api_client.put(
                self.URL, {}, format="json",
                **auth_headers(permissions=[NOTIFICATION_PREFERENCES_GLOBAL_PUT]),
            )

        assert response.status_code == 200
