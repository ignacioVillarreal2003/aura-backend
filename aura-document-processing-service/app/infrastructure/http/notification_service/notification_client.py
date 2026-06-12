import logging
from typing import Any, Optional

import httpx

from app.infrastructure.http.notification_service.notification_client_settings import (
    NotificationClientSettings,
)

logger = logging.getLogger(__name__)


class NotificationClient:
    """
    Producer client for aura-notification-service.

    Sends semantic events to ``POST /api/v1/internal/events/`` authenticated with
    the ``X-Internal-Token`` header. Failures are logged and never raised: a
    notification problem must not break document processing.
    """

    def __init__(self, settings: Optional[NotificationClientSettings] = None) -> None:
        self._settings = settings or NotificationClientSettings()
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def enabled(self) -> bool:
        return bool(self._settings.service_url and self._settings.internal_api_token)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._settings.request_timeout_seconds,
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def emit_event(
            self,
            *,
            event_type: str,
            recipient_ids: list[int],
            actor_id: Optional[int] = None,
            actor_name: str = "",
            context: Optional[dict[str, Any]] = None,
            link_url: Optional[str] = None,
    ) -> None:
        if not self.enabled:
            logger.debug(
                "Notification service not configured "
                "(NOTIFICATION_SERVICE_URL or NOTIFICATION_INTERNAL_API_TOKEN missing); skipping event.",
                extra={"event_type": event_type},
            )
            return

        payload: dict[str, Any] = {
            "event_type": event_type,
            "recipient_ids": recipient_ids,
        }
        if actor_id is not None:
            payload["actor_id"] = actor_id
        if actor_name:
            payload["actor_name"] = actor_name
        if context:
            payload["context"] = context
        if link_url:
            payload["link_url"] = link_url

        url = f"{self._settings.service_url.rstrip('/')}/api/v1/internal/events/"
        headers = {"X-Internal-Token": self._settings.internal_api_token}

        try:
            response = await self._get_client().post(url, json=payload, headers=headers)
            if response.status_code >= 400:
                logger.warning(
                    "Notification service rejected event.",
                    extra={
                        "event_type": event_type,
                        "status_code": response.status_code,
                        "body": response.text[:200],
                    },
                )
        except httpx.HTTPError as exc:
            logger.warning(
                "Failed to emit notification event.",
                extra={"event_type": event_type, "error": str(exc)},
            )
