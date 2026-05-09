"""Tiny Redis pub/sub helper used by the SSE endpoint.

We deliberately avoid Django Channels here: notifications only need a
server-to-client push, and we already speak Redis natively for cache.
Any worker process publishes via `publish_user_event`, the SSE view
subscribes with `subscribe_user_events`. Channels are namespaced with
the configurable `NOTIFICATION_REDIS_CHANNEL_PREFIX`.
"""

import json
import logging
from typing import Iterator

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

_PUBLISHER: redis.Redis | None = None


def _publisher() -> redis.Redis:
    global _PUBLISHER
    if _PUBLISHER is None:
        _PUBLISHER = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _PUBLISHER


def user_channel(user_id: int) -> str:
    return f"{settings.NOTIFICATION_REDIS_CHANNEL_PREFIX}:{user_id}"


def publish_user_event(user_id: int, payload: dict) -> int:
    """Publish a JSON payload to the per-user notifications channel.

    Returns the number of subscribers that received it (0 means the user
    has no open SSE connection, which is fine — the in-app row is still
    persisted).
    """

    try:
        body = json.dumps(payload, default=str)
        return int(_publisher().publish(user_channel(user_id), body))
    except Exception as exc:
        logger.warning("Failed to publish realtime event for user %s: %s", user_id, exc)
        return 0


def subscribe_user_events(user_id: int, *, heartbeat_seconds: float) -> Iterator[dict | None]:
    """Yields published payloads for the user, or `None` whenever the
    `heartbeat_seconds` window elapses with no message (so the caller can
    push a keep-alive frame). The iterator runs forever until the caller
    breaks out of it.
    """

    client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    channel = user_channel(user_id)
    try:
        pubsub.subscribe(channel)
        while True:
            message = pubsub.get_message(timeout=heartbeat_seconds)
            if message is None:
                yield None
                continue
            data = message.get("data")
            if not data:
                continue
            try:
                yield json.loads(data)
            except (TypeError, ValueError):
                logger.warning("Dropping malformed pubsub frame on %s.", channel)
    finally:
        try:
            pubsub.unsubscribe(channel)
            pubsub.close()
        except Exception:
            logger.debug("Failed to cleanly close pubsub connection.", exc_info=True)
        try:
            client.close()
        except Exception:
            pass
