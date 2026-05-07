import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class NotificationClient:
    def __init__(self):
        self.base = getattr(settings, "NOTIFICATION_SERVICE_URL", "").rstrip("/")

    def notify_members_added(
        self,
        receiver_ids: list[int],
        chat_name: str,
        sender_id: int,
        sender_name: str,
        access_token: str,
    ) -> None:
        if not self.base:
            logger.warning("NOTIFICATION_SERVICE_URL not configured, skipping notification.")
            return

        payload = {
            "receiver_ids": receiver_ids,
            "message": f"Te agregaron al chat \"{chat_name}\"",
            "type": "user",
            "sender_name": sender_name,
            "target_scope": "individual",
        }

        try:
            response = requests.post(
                f"{self.base}/api/notifications/",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=5,
            )
            if not response.ok:
                logger.warning(
                    "Notification service returned non-OK response.",
                    extra={"status": response.status_code, "body": response.text[:200]},
                )
        except requests.RequestException as exc:
            logger.error("Failed to send notification: %s", exc)


notification_client = NotificationClient()
