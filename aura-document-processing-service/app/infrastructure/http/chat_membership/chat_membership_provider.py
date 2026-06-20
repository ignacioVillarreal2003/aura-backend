import logging
from typing import Any, Optional
import httpx

from app.infrastructure.http.chat_membership.interfaces.chat_membership_provider_interface import (
    ChatMembershipProviderInterface,
)
from app.infrastructure.http.chat_membership.chat_membership_provider_settings import (
    ChatMembershipProviderSettings,
)
from app.infrastructure.http.chat_membership.dtos.chat_membership_response import (
    ChatMembershipResponse,
)
from app.infrastructure.http.http_client.exceptions.http_client_exceptions import HttpClientException
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)

_NOT_A_MEMBER = ChatMembershipResponse(is_member=False, role=None)


class ChatMembershipProvider(ChatMembershipProviderInterface):
    def __init__(
            self,
            http_client: HttpClientInterface,
            settings: Optional[ChatMembershipProviderSettings] = None,
    ) -> None:
        self._http_client = http_client
        self._settings = settings or ChatMembershipProviderSettings()

    async def get_membership(
            self,
            *,
            chat_id: int,
            user_id: int,
            authorization_header: str | None,
    ) -> ChatMembershipResponse:
        if not self._settings.membership_url:
            logger.debug(
                "Skipping chat membership check: membership URL is not configured.",
                extra={"chat_id": chat_id, "user_id": user_id},
            )
            return _NOT_A_MEMBER

        headers = self._build_request_headers(authorization_header=authorization_header)
        if headers is None:
            logger.debug(
                "Skipping chat membership check: no credentials available.",
                extra={"chat_id": chat_id, "user_id": user_id},
            )
            return _NOT_A_MEMBER

        base = self._settings.membership_url.rstrip("/")
        url = f"{base}/internal/chats/{chat_id}/members/{user_id}/"
        timeout = self._settings.request_timeout_seconds

        try:
            response = await self._http_client.get(
                url,
                headers=headers,
                timeout=timeout,
            )
            if response.status_code == 404:
                return _NOT_A_MEMBER
            if response.status_code >= 400:
                logger.warning(
                    "Chat membership request failed.",
                    extra={
                        "chat_id": chat_id,
                        "user_id": user_id,
                        "status_code": response.status_code,
                    },
                )
                return _NOT_A_MEMBER

            payload_any: Any = response.json()
            if not isinstance(payload_any, dict):
                logger.warning(
                    "Unexpected chat membership payload shape.",
                    extra={"chat_id": chat_id, "user_id": user_id},
                )
                return _NOT_A_MEMBER

            is_member = bool(payload_any.get("is_member", False))
            role_raw = payload_any.get("role")
            role = str(role_raw) if isinstance(role_raw, str) and role_raw.strip() else None
            return ChatMembershipResponse(is_member=is_member, role=role)

        except (HttpClientException, httpx.RequestError):
            logger.exception(
                "Error while checking chat membership.",
                extra={"chat_id": chat_id, "user_id": user_id},
            )
            return _NOT_A_MEMBER
        except ValueError:
            logger.exception(
                "Invalid JSON while checking chat membership.",
                extra={"chat_id": chat_id, "user_id": user_id},
            )
            return _NOT_A_MEMBER

    def _build_request_headers(
            self,
            *,
            authorization_header: str | None,
    ) -> dict[str, str] | None:
        bearer = self._normalize_bearer(authorization_header)
        if bearer is None:
            return None
        return {
            "Authorization": bearer,
            "Accept": "application/json",
        }

    @staticmethod
    def _normalize_bearer(raw: Optional[str]) -> Optional[str]:
        if raw is None:
            return None
        stripped = raw.strip()
        if not stripped:
            return None
        if stripped.lower().startswith("bearer "):
            return stripped
        return f"Bearer {stripped}"
