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


@lru_cache(maxsize=1)
def _redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def check_message_rate_limit(user_id: int, chat_id: int) -> bool:
    key = f"aura:ws_msg_rate:{user_id}:{chat_id}"
    try:
        r = _redis()
        count = r.incr(key)
        if count == 1:
            r.expire(key, _MESSAGE_RATE_LIMIT_WINDOW)
        return count <= _MESSAGE_RATE_LIMIT_MAX
    except redis.RedisError:
        logger.warning(
            "Redis error checking message rate limit, failing open.",
            extra={"user_id": user_id, "chat_id": chat_id},
        )
        return True


def check_typing_rate_limit(user_id: int) -> bool:
    key = f"aura:ws_typing_rate:{user_id}"
    try:
        r = _redis()
        count = r.incr(key)
        if count == 1:
            r.expire(key, _TYPING_RATE_LIMIT_WINDOW)
        return count <= _TYPING_RATE_LIMIT_MAX
    except redis.RedisError:
        logger.warning(
            "Redis error checking typing rate limit, failing open.",
            extra={"user_id": user_id},
        )
        return True
