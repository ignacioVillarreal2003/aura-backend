from __future__ import annotations

import logging
from functools import lru_cache
import redis
from django.conf import settings

logger = logging.getLogger(__name__)

_PRESENCE_TTL = 3600

_JOIN_SCRIPT = """
redis.call('sadd', KEYS[1], ARGV[1])
redis.call('expire', KEYS[1], ARGV[2])
return redis.call('scard', KEYS[1])
"""

_LEAVE_SCRIPT = """
redis.call('srem', KEYS[1], ARGV[1])
local remaining = redis.call('scard', KEYS[1])
if remaining == 0 then
    redis.call('del', KEYS[1])
end
return remaining
"""

_REFRESH_SCRIPT = """
redis.call('sadd', KEYS[1], ARGV[1])
redis.call('expire', KEYS[1], ARGV[2])
return 1
"""


@lru_cache(maxsize=1)
def _redis_pool() -> redis.ConnectionPool:
    return redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


def _redis() -> redis.Redis:
    return redis.Redis(connection_pool=_redis_pool())


def _key(chat_id: int, user_id: int) -> str:
    return f"aura:presence:{chat_id}:{user_id}"


def join(chat_id: int, user_id: int, conn_id: str) -> bool:
    try:
        count = _redis().eval(_JOIN_SCRIPT, 1, _key(chat_id, user_id), conn_id, _PRESENCE_TTL)
        return int(count) == 1
    except redis.RedisError:
        logger.warning(
            "Redis error registering presence; assuming first presence.",
            extra={"chat_id": chat_id, "user_id": user_id},
        )
        return True


def leave(chat_id: int, user_id: int, conn_id: str) -> bool:
    try:
        remaining = _redis().eval(_LEAVE_SCRIPT, 1, _key(chat_id, user_id), conn_id)
        return int(remaining) == 0
    except redis.RedisError:
        logger.warning(
            "Redis error deregistering presence; assuming last presence.",
            extra={"chat_id": chat_id, "user_id": user_id},
        )
        return True


def refresh(chat_id: int, user_id: int, conn_id: str) -> None:
    try:
        _redis().eval(_REFRESH_SCRIPT, 1, _key(chat_id, user_id), conn_id, _PRESENCE_TTL)
    except redis.RedisError:
        logger.warning(
            "Redis error refreshing presence lease.",
            extra={"chat_id": chat_id, "user_id": user_id},
        )
