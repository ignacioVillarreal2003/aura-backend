from __future__ import annotations

import logging
from functools import lru_cache
import redis
from django.conf import settings

from core.exceptions import ServiceUnavailableException

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _key(chat_id: int) -> str:
    return f"aura:chat_ai_reply_lock:{chat_id}"


def _lock_ttl() -> int:
    explicit = getattr(settings, "CHAT_AI_REPLY_LOCK_TTL_SECONDS", None)
    if explicit is not None:
        return max(int(explicit), 60)
    # Default: stream read timeout + 60 s grace period so the lock never outlasts
    # an active stream. Prevents a 15-min lockout when LLM streams stall silently.
    stream_read_timeout = int(getattr(settings, "LLM_STREAM_READ_TIMEOUT", 180))
    return stream_read_timeout + 60


def try_acquire(chat_id: int) -> bool:
    try:
        return bool(_redis().set(_key(chat_id), "1", nx=True, ex=_lock_ttl()))
    except redis.RedisError:
        logger.exception(
            "Redis error acquiring chat AI reply lock.",
            extra={"chat_id": chat_id},
        )
        raise ServiceUnavailableException(
            detail="Could not coordinate chat reply; try again shortly.",
        ) from None


def release(chat_id: int) -> None:
    try:
        _redis().delete(_key(chat_id))
    except redis.RedisError:
        logger.exception(
            "Redis error releasing chat AI reply lock.",
            extra={"chat_id": chat_id},
        )


def is_locked(chat_id: int) -> bool:
    try:
        return bool(_redis().exists(_key(chat_id)))
    except redis.RedisError:
        logger.warning(
            "Redis error checking chat AI reply lock; treating as unlocked.",
            extra={"chat_id": chat_id},
        )
        return False
