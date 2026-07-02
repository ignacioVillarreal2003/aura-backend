import json
import pytest
from unittest.mock import patch

from core.authorization.permissions import NOTIFICATION_STREAM_SUBSCRIBE
from apps.notification.api.views.stream_view import _format_sse

_SUBSCRIBE = "apps.notification.api.views.stream_view.subscribe_user_events"

URL = "/api/v1/notifications/stream/"


class TestFormatSse:
    def test_encodes_event_name(self):
        result = _format_sse("notification.created").decode("utf-8")
        assert "event: notification.created" in result

    def test_encodes_data_as_json(self):
        result = _format_sse("test.event", {"id": 42}).decode("utf-8")
        assert '"id": 42' in result

    def test_appends_double_newline(self):
        result = _format_sse("x")
        assert result.endswith(b"\n\n")

    def test_no_data_field_when_data_is_none(self):
        result = _format_sse("heartbeat").decode("utf-8")
        assert "data:" not in result

    def test_data_field_present_when_dict_passed(self):
        result = _format_sse("ev", {"key": "val"}).decode("utf-8")
        assert "data:" in result

    def test_result_is_bytes(self):
        result = _format_sse("test")
        assert isinstance(result, bytes)

    def test_nested_data_serialized(self):
        result = _format_sse("ev", {"nested": {"a": 1}}).decode("utf-8")
        assert "nested" in result


class TestNotificationStreamView:
    def test_returns_401_without_auth(self, api_client):
        response = api_client.get(URL)
        assert response.status_code == 401

    def test_returns_403_missing_permission(self, api_client, auth_headers):
        with patch(_SUBSCRIBE, return_value=iter([])):
            response = api_client.get(URL, **auth_headers(permissions=["WRONG"]))
        assert response.status_code == 403

    def test_post_not_allowed(self, api_client, auth_headers):
        response = api_client.post(
            URL, {}, format="json",
            **auth_headers(permissions=[NOTIFICATION_STREAM_SUBSCRIBE]),
        )
        assert response.status_code == 405
