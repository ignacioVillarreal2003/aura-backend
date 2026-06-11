import concurrent.futures
import logging
import time
from typing import Any
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3
_BACKOFF_SECONDS = [0, 2, 4]
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="notif")


class NotificationClient:
    def emit_event(
            self,
            event_type: str,
            recipient_ids: list[int],
            actor_id: int | None = None,
            actor_name: str = "",
            context: dict[str, Any] | None = None,
            link_url: str | None = None,
    ) -> None:
        base = getattr(settings, "NOTIFICATION_SERVICE_URL", "").strip().rstrip("/")
        token = getattr(settings, "NOTIFICATION_INTERNAL_API_TOKEN", "")
        if not base or not token:
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
        if link_url:
            payload["link_url"] = link_url

        _executor.submit(self._dispatch, payload, base, token)

    def _dispatch(self, payload: dict[str, Any], base: str, token: str) -> None:
        headers = {
            "Content-Type": "application/json",
            "X-Internal-Token": token,
        }
        event_type = payload.get("event_type", "unknown")

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            if attempt > 1:
                time.sleep(_BACKOFF_SECONDS[attempt - 1])
            try:
                response = httpx.post(
                    f"{base}/api/v1/internal/events/",
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
                    return
                logger.debug(
                    "Notification attempt %d for '%s' failed, retrying: %s",
                    attempt, event_type, exc,
                )

        logger.error(
            "Failed to emit event '%s' after %d attempts (HTTP errors).",
            event_type, _MAX_ATTEMPTS,
        )


notification_client = NotificationClient()
