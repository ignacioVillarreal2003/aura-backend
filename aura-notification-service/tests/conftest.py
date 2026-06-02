import types
import pytest
from rest_framework.test import APIClient

from core.authorization.permissions import (
    NOTIFICATION_DETAIL_GET,
    NOTIFICATION_INBOX_LIST,
    NOTIFICATION_MARK_ALL_READ_POST,
    NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT,
    NOTIFICATION_PREFERENCES_EVENT_TYPES_GET,
    NOTIFICATION_PREFERENCES_GLOBAL_GET,
    NOTIFICATION_PREFERENCES_GLOBAL_PUT,
    NOTIFICATION_SOFT_DELETE,
    NOTIFICATION_STATUS_PATCH,
    NOTIFICATION_UNREAD_COUNT_GET,
)

ALL_PERMISSIONS = [
    NOTIFICATION_INBOX_LIST,
    NOTIFICATION_UNREAD_COUNT_GET,
    NOTIFICATION_DETAIL_GET,
    NOTIFICATION_STATUS_PATCH,
    NOTIFICATION_SOFT_DELETE,
    NOTIFICATION_MARK_ALL_READ_POST,
    NOTIFICATION_PREFERENCES_GLOBAL_GET,
    NOTIFICATION_PREFERENCES_GLOBAL_PUT,
    NOTIFICATION_PREFERENCES_EVENT_TYPES_GET,
    NOTIFICATION_PREFERENCES_EVENT_TYPE_PUT,
]


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_headers():
    """
    Returns a factory for building service-auth HTTP headers.

    Usage:
        response = api_client.get(url, **auth_headers(user_id=42, permissions=[PERM]))
    """
    def _make(user_id=42, permissions=None, email="user@test.com"):
        headers = {
            "HTTP_X_SERVICE_API_KEY": "test-service-key",
            "HTTP_X_USER_ID": str(user_id),
            "HTTP_X_USER_EMAIL": email,
        }
        if permissions is not None:
            if isinstance(permissions, (list, tuple)):
                headers["HTTP_X_USER_PERMISSIONS"] = ",".join(permissions)
            else:
                headers["HTTP_X_USER_PERMISSIONS"] = str(permissions)
        return headers

    return _make


@pytest.fixture
def make_notification():
    """
    Factory for in-memory notification objects accepted by NotificationSerializer.
    All fields match the Notification model definition.
    """
    def _make(**overrides):
        defaults = dict(
            id=1,
            receiver_id=42,
            title="Test Notification",
            message="This is a test message",
            type="event",
            event_type="chat.member.invited",
            event_key=None,
            data={},
            severity="info",
            link_url=None,
            sender_name=None,
            target_scope="individual",
            target_label=None,
            status="unread",
            read_at=None,
            created_by=None,
            created_at=None,
            updated_at=None,
        )
        defaults.update(overrides)
        return types.SimpleNamespace(**defaults)

    return _make


@pytest.fixture
def make_preference():
    """
    Factory for in-memory preference objects accepted by NotificationPreferenceSerializer.
    """
    def _make(**overrides):
        defaults = dict(
            user_id=42,
            inapp_enabled=True,
            email_enabled=True,
            mute_until=None,
            updated_at=None,
        )
        defaults.update(overrides)
        return types.SimpleNamespace(**defaults)

    return _make


@pytest.fixture
def internal_token_header():
    return {"HTTP_X_INTERNAL_TOKEN": "test-internal-token"}


@pytest.fixture
def wrong_token_header():
    return {"HTTP_X_INTERNAL_TOKEN": "wrong-token"}
