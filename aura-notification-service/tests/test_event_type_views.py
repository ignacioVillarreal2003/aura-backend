"""
Tests for the public event type catalogue:
  GET /api/v1/event-types/
"""
import pytest

from apps.notification.events import iter_events
from apps.notification.events.registry import EventType

URL = "/api/v1/event-types/"

EXPECTED_EVENT_TYPES = {
    EventType.CHAT_MEMBER_INVITED,
    EventType.CHAT_MEMBER_REMOVED,
    EventType.CHAT_LOCKED,
    EventType.AUTH_PASSWORD_CHANGED,
    EventType.AUTH_NEW_LOGIN,
    EventType.DOCUMENT_PROCESSING_DONE,
    EventType.DOCUMENT_PROCESSING_FAILED,
    EventType.ADMIN_BROADCAST,
    EventType.SYSTEM_ANNOUNCEMENT,
}


class TestEventTypeCatalogueView:
    def test_no_authentication_required(self, api_client):
        response = api_client.get(URL)
        assert response.status_code == 200

    def test_returns_all_registered_event_types(self, api_client):
        response = api_client.get(URL)

        assert response.status_code == 200
        returned_types = {entry["event_type"] for entry in response.data}
        assert returned_types == EXPECTED_EVENT_TYPES

    def test_each_entry_has_required_fields(self, api_client):
        response = api_client.get(URL)

        required_fields = {
            "event_type",
            "type",
            "severity",
            "description",
            "default_channels",
            "available_channels",
            "is_silenceable",
        }
        for entry in response.data:
            assert required_fields.issubset(entry.keys()), (
                f"Entry {entry.get('event_type')} is missing fields: "
                f"{required_fields - entry.keys()}"
            )

    def test_non_silenceable_events_flagged_correctly(self, api_client):
        response = api_client.get(URL)

        non_silenceable = {
            e["event_type"] for e in response.data if not e["is_silenceable"]
        }
        assert EventType.AUTH_PASSWORD_CHANGED in non_silenceable
        assert EventType.SYSTEM_ANNOUNCEMENT in non_silenceable

    def test_auth_password_changed_has_email_in_default_channels(self, api_client):
        response = api_client.get(URL)

        entry = next(
            e for e in response.data if e["event_type"] == EventType.AUTH_PASSWORD_CHANGED
        )
        assert "email" in entry["default_channels"]
        assert "inapp" in entry["default_channels"]

    def test_chat_events_only_inapp_by_default(self, api_client):
        response = api_client.get(URL)

        chat_invite = next(
            e for e in response.data if e["event_type"] == EventType.CHAT_MEMBER_INVITED
        )
        assert chat_invite["default_channels"] == ["inapp"]

    def test_available_channels_always_contains_inapp_and_email(self, api_client):
        response = api_client.get(URL)

        for entry in response.data:
            assert "inapp" in entry["available_channels"], entry["event_type"]
            assert "email" in entry["available_channels"], entry["event_type"]

    def test_catalogue_does_not_include_user_channel_overrides(self, api_client):
        response = api_client.get(URL)

        for entry in response.data:
            assert "channels" not in entry, (
                "Public catalogue must not expose per-user channel states. "
                "Use /me/notification-preferences/event-types/ for that."
            )
