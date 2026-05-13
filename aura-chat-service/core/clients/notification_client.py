import logging
import threading
import time
from typing import Any
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = [0, 2, 4]


class NotificationClient:
    def __init__(self):
        self.base = getattr(settings, "NOTIFICATION_SERVICE_URL", "").rstrip("/")
        self.token = getattr(settings, "NOTIFICATION_INTERNAL_API_TOKEN", "")

    def emit_event(
        self,
        event_type: str,
        recipient_ids: list[int],
        actor_id: int | None = None,
        actor_name: str = "",
        context: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        channels_override: list[str] | None = None,
    ) -> None:
        """Fire-and-forget: dispatches the event in a background daemon thread."""
        if not self.base or not self.token:
            logger.warning(
                "Notification service not fully configured "
                "(NOTIFICATION_SERVICE_URL or NOTIFICATION_INTERNAL_API_TOKEN missing), skipping.",
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
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        if channels_override:
            payload["channels_override"] = channels_override

        threading.Thread(target=self._dispatch, args=(payload,), daemon=True).start()

    def _dispatch(self, payload: dict[str, Any]) -> None:
        headers = {
            "Content-Type": "application/json",
            "X-Internal-Token": self.token,
        }
        event_type = payload.get("event_type", "unknown")

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            if attempt > 1:
                time.sleep(_BACKOFF_SECONDS[attempt - 1])
            try:
                response = httpx.post(
                    f"{self.base}/api/v1/internal/events/",
                    json=payload,
                    headers=headers,
                    timeout=5,
                )
                if response.is_success:
                    return
                logger.warning(
                    "Notification service returned non-OK response for '%s' (attempt %d/%d).",
                    event_type, attempt, _MAX_ATTEMPTS,
                    extra={"status": response.status_code, "body": response.text[:200]},
                )
                if response.status_code < 500:
                    return
            except httpx.RequestError as exc:
                if attempt == _MAX_ATTEMPTS:
                    logger.error(
                        "Failed to emit event '%s' after %d attempts: %s",
                        event_type, _MAX_ATTEMPTS, exc,
                    )
                else:
                    logger.debug(
                        "Notification attempt %d for '%s' failed, retrying: %s",
                        attempt, event_type, exc,
                    )


notification_client = NotificationClient()
