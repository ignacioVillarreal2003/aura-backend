from __future__ import annotations

import logging
from functools import lru_cache
import redis
from django.conf import settings

logger = logging.getLogger(__name__)

# Presence is reference-counted per (chat, user): a user may have several open
# tabs/connections in the same chat. We only consider a user "joined" when their
# first connection arrives and "left" when their last connection drops, so that
# closing one of several tabs does NOT make the user disappear for everyone else.
_PRESENCE_TTL = 3600

# Atomically register a connection and return the resulting connection count for
# the (chat, user). A return value of 1 means this is the user's first presence.
_JOIN_SCRIPT = """
redis.call('sadd', KEYS[1], ARGV[1])
redis.call('expire', KEYS[1], ARGV[2])
return redis.call('scard', KEYS[1])
"""

# Atomically deregister a connection and return the remaining count. A return
# value of 0 means the user has no more connections (truly left).
_LEAVE_SCRIPT = """
redis.call('srem', KEYS[1], ARGV[1])
local remaining = redis.call('scard', KEYS[1])
if remaining == 0 then
    redis.call('del', KEYS[1])
end
return remaining
"""

# Re-assert an existing connection (keep it in the set, bump the TTL) without
# changing presence semantics. Used by the heartbeat for idle viewers.
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
    """Register a connection. Returns True when it is the user's first one."""
    try:
        count = _redis().eval(_JOIN_SCRIPT, 1, _key(chat_id, user_id), conn_id, _PRESENCE_TTL)
        return int(count) == 1
    except redis.RedisError:
        logger.warning(
            "Redis error registering presence; assuming first presence.",
            extra={"chat_id": chat_id, "user_id": user_id},
        )
        # Fail towards emitting a join so peers learn about the user.
        return True


def leave(chat_id: int, user_id: int, conn_id: str) -> bool:
    """Deregister a connection. Returns True when it was the user's last one."""
    try:
        remaining = _redis().eval(_LEAVE_SCRIPT, 1, _key(chat_id, user_id), conn_id)
        return int(remaining) == 0
    except redis.RedisError:
        logger.warning(
            "Redis error deregistering presence; assuming last presence.",
            extra={"chat_id": chat_id, "user_id": user_id},
        )
        # Fail towards emitting a leave so peers do not keep a ghost present.
        return True


def refresh(chat_id: int, user_id: int, conn_id: str) -> None:
    """Bump the presence lease for a still-open connection."""
    try:
        _redis().eval(_REFRESH_SCRIPT, 1, _key(chat_id, user_id), conn_id, _PRESENCE_TTL)
    except redis.RedisError:
        logger.warning(
            "Redis error refreshing presence lease.",
            extra={"chat_id": chat_id, "user_id": user_id},
        )
