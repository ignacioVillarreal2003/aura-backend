from __future__ import annotations

import logging
from functools import lru_cache
import redis
from django.conf import settings

logger = logging.getLogger(__name__)

_MESSAGE_RATE_LIMIT_MAX = 10
_MESSAGE_RATE_LIMIT_WINDOW = 60
_TYPING_RATE_LIMIT_MAX = 20
_TYPING_RATE_LIMIT_WINDOW = 10
_WS_CONNECTION_TTL = 3600


@lru_cache(maxsize=1)
def _redis_pool() -> redis.ConnectionPool:
    return redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


def _redis() -> redis.Redis:
    return redis.Redis(connection_pool=_redis_pool())


def _fixed_window_allows(key: str, window: int, limit: int) -> bool:
    r = _redis()
    count = r.incr(key)
    if count == 1:
        r.expire(key, window)
    return count <= limit


def check_message_rate_limit(user_id: int, chat_id: int) -> bool:
    key = f"aura:ws_msg_rate:{user_id}:{chat_id}"
    try:
        return _fixed_window_allows(
            key, _MESSAGE_RATE_LIMIT_WINDOW, _MESSAGE_RATE_LIMIT_MAX
        )
    except redis.RedisError:
        logger.warning(
            "Redis error checking message rate limit, failing open.",
            extra={"user_id": user_id, "chat_id": chat_id},
        )
        return True


def check_typing_rate_limit(user_id: int) -> bool:
    key = f"aura:ws_typing_rate:{user_id}"
    try:
        return _fixed_window_allows(
            key, _TYPING_RATE_LIMIT_WINDOW, _TYPING_RATE_LIMIT_MAX
        )
    except redis.RedisError:
        logger.warning(
            "Redis error checking typing rate limit, failing open.",
            extra={"user_id": user_id},
        )
        return True


def acquire_ws_connection(user_id: int) -> bool:
    max_conns = int(getattr(settings, "WS_MAX_CONNECTIONS_PER_USER", 5))
    key = f"aura:ws_connections:{user_id}"
    try:
        r = _redis()
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, _WS_CONNECTION_TTL)
        count, _ = pipe.execute()
        if count > max_conns:
            r.decr(key)
            return False
        return True
    except redis.RedisError:
        logger.warning(
            "Redis error acquiring WS connection slot, failing open.",
            extra={"user_id": user_id},
        )
        return True


def release_ws_connection(user_id: int) -> None:
    key = f"aura:ws_connections:{user_id}"
    try:
        r = _redis()
        current = r.get(key)
        if current is not None and int(current) > 0:
            r.decr(key)
    except redis.RedisError:
        logger.warning(
            "Redis error releasing WS connection slot.",
            extra={"user_id": user_id},
        )
