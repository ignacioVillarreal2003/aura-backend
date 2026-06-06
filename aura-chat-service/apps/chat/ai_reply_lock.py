from __future__ import annotations

import logging
import secrets
from functools import lru_cache
import redis
from django.conf import settings

from core.exceptions import ServiceUnavailableException

logger = logging.getLogger(__name__)

_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

_REFRESH_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('expire', KEYS[1], ARGV[2])
else
    return 0
end
"""


@lru_cache(maxsize=1)
def _redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _key(chat_id: int) -> str:
    return f"aura:chat_ai_reply_lock:{chat_id}"


def _lock_ttl() -> int:
    explicit = getattr(settings, "CHAT_AI_REPLY_LOCK_TTL_SECONDS", None)
    if explicit is not None:
        return max(int(explicit), 60)
    stream_read_timeout = int(getattr(settings, "LLM_STREAM_READ_TIMEOUT", 180))
    return stream_read_timeout + 60


def try_acquire(chat_id: int) -> str | None:
    token = secrets.token_hex(16)
    try:
        acquired = _redis().set(_key(chat_id), token, nx=True, ex=_lock_ttl())
    except redis.RedisError:
        logger.exception(
            "Redis error acquiring chat AI reply lock.",
            extra={"chat_id": chat_id},
        )
        raise ServiceUnavailableException(
            detail="Could not coordinate chat reply; try again shortly.",
        ) from None
    return token if acquired else None


def release(chat_id: int, token: str | None = None) -> None:
    try:
        if token is None:
            _redis().delete(_key(chat_id))
        else:
            _redis().eval(_RELEASE_SCRIPT, 1, _key(chat_id), token)
    except redis.RedisError:
        logger.exception(
            "Redis error releasing chat AI reply lock.",
            extra={"chat_id": chat_id},
        )


def refresh(chat_id: int, token: str) -> bool:
    try:
        result = _redis().eval(_REFRESH_SCRIPT, 1, _key(chat_id), token, _lock_ttl())
        return bool(result)
    except redis.RedisError:
        logger.warning(
            "Redis error refreshing chat AI reply lock.",
            extra={"chat_id": chat_id},
        )
        return False


def is_locked(chat_id: int) -> bool:
    try:
        return bool(_redis().exists(_key(chat_id)))
    except redis.RedisError:
        logger.warning(
            "Redis error checking chat AI reply lock; treating as unlocked.",
            extra={"chat_id": chat_id},
        )
        return False
