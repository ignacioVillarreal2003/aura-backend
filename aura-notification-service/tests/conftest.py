import types
import pytest
from rest_framework.test import APIClient

from core.authentication.authenticated_user import AuthenticatedUser
from core.authentication.authentication_exceptions import (
    AuthenticationProviderInvalidTokenException,
)
from core.authentication.authentication_provider import authentication_provider
from core.authorization.permissions import (
    NOTIFICATION_DETAIL_GET,
    NOTIFICATION_INBOX_LIST,
    NOTIFICATION_MARK_ALL_READ_POST,
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
]


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_headers(monkeypatch):
    users_by_token: dict[str, AuthenticatedUser] = {}

    def _fake_validate_token(token: str) -> AuthenticatedUser:
        try:
            return users_by_token[token]
        except KeyError:
            raise AuthenticationProviderInvalidTokenException("Invalid or expired token")

    monkeypatch.setattr(authentication_provider, "validate_token", _fake_validate_token)

    def _make(user_id=42, permissions=None, email="user@test.com"):
        if permissions is None:
            perms = ()
        elif isinstance(permissions, (list, tuple)):
            perms = tuple(permissions)
        else:
            perms = (str(permissions),)
        token = f"test-jwt-{user_id}-{len(users_by_token)}"
        users_by_token[token] = AuthenticatedUser(
            id=user_id,
            email=email,
            permissions=perms,
        )
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    return _make


@pytest.fixture
def make_notification():
    def _make(**overrides):
        defaults = dict(
            id=1,
            receiver_id=42,
            event_type="chat.member.invited",
            message="This is a test message",
            data={},
            severity="info",
            link_url=None,
            actor_name=None,
            status="unread",
            read_at=None,
            created_by=None,
            created_at=None,
        )
        defaults.update(overrides)
        return types.SimpleNamespace(**defaults)

    return _make


@pytest.fixture
def make_preference():
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
