from __future__ import annotations
import logging

from core.pubsub import publish_user_event

logger = logging.getLogger(__name__)


class RealtimeService:
    EVENT_CREATED = "notification.created"
    EVENT_UPDATED = "notification.updated"
    EVENT_DELETED = "notification.deleted"

    def publish_created(self, user_id: int, payload: dict) -> None:
        publish_user_event(user_id, {"event": self.EVENT_CREATED, "data": payload})

    def publish_updated(self, user_id: int, payload: dict) -> None:
        publish_user_event(user_id, {"event": self.EVENT_UPDATED, "data": payload})

    def publish_deleted(self, user_id: int, notification_id: int) -> None:
        publish_user_event(
            user_id,
            {"event": self.EVENT_DELETED, "data": {"id": notification_id}},
        )


realtime_service = RealtimeService()
