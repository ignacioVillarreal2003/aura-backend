"""Realtime notifications publisher.

The dispatcher calls `realtime_service.publish_*` whenever an in-app
notification row is created, updated or deleted. The actual transport
is Redis pub/sub (see `core.pubsub.redis_pubsub`); the SSE endpoint
subscribes per user and forwards the JSON payloads to the browser.
"""

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
