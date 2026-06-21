"""
Unit tests for ChatMembershipProvider.

The provider is fail-closed: whenever membership cannot be determined it must
report the user as NOT a member, so authorization denies rather than grants.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.http.chat_membership.chat_membership_provider import (
    ChatMembershipProvider,
)
from app.infrastructure.http.chat_membership.chat_membership_provider_settings import (
    ChatMembershipProviderSettings,
)
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import HttpClientException


_AUTH_HEADER = "Bearer user-token"


def _provider(http_client, *, membership_url="http://chat-service"):
    settings = ChatMembershipProviderSettings(
        membership_url=membership_url,
    )
    return ChatMembershipProvider(http_client=http_client, settings=settings)


def _response(status_code, payload=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=payload)
    return resp


class TestChatMembershipProvider:
    @pytest.mark.asyncio
    async def test_owner_is_member_and_owner(self):
        http_client = AsyncMock()
        http_client.get.return_value = _response(
            200, {"chat_id": 5, "user_id": 1, "is_member": True, "role": "owner"}
        )
        result = await _provider(http_client).get_membership(
            chat_id=5, user_id=1, authorization_header=_AUTH_HEADER
        )
        assert result.is_member is True
        assert result.is_owner is True

    @pytest.mark.asyncio
    async def test_member_is_member_but_not_owner(self):
        http_client = AsyncMock()
        http_client.get.return_value = _response(
            200, {"is_member": True, "role": "member"}
        )
        result = await _provider(http_client).get_membership(
            chat_id=5, user_id=1, authorization_header=_AUTH_HEADER
        )
        assert result.is_member is True
        assert result.is_owner is False

    @pytest.mark.asyncio
    async def test_not_member_payload(self):
        http_client = AsyncMock()
        http_client.get.return_value = _response(200, {"is_member": False, "role": None})
        result = await _provider(http_client).get_membership(
            chat_id=5, user_id=1, authorization_header=_AUTH_HEADER
        )
        assert result.is_member is False
        assert result.is_owner is False

    @pytest.mark.asyncio
    async def test_url_not_configured_is_fail_closed(self):
        http_client = AsyncMock()
        result = await _provider(http_client, membership_url=None).get_membership(
            chat_id=5, user_id=1, authorization_header=_AUTH_HEADER
        )
        assert result.is_member is False
        http_client.get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_404_is_not_member(self):
        http_client = AsyncMock()
        http_client.get.return_value = _response(404)
        result = await _provider(http_client).get_membership(
            chat_id=5, user_id=1, authorization_header=_AUTH_HEADER
        )
        assert result.is_member is False

    @pytest.mark.asyncio
    async def test_transport_error_is_fail_closed(self):
        http_client = AsyncMock()
        http_client.get.side_effect = HttpClientException("boom")
        result = await _provider(http_client).get_membership(
            chat_id=5, user_id=1, authorization_header=_AUTH_HEADER
        )
        assert result.is_member is False
