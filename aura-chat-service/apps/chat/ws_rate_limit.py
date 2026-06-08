from __future__ import annotations

import logging
import time
from functools import lru_cache
import redis
from django.conf import settings

logger = logging.getLogger(__name__)

_WS_CONNECTION_TTL = 3600


@lru_cache(maxsize=1)
def _redis_pool() -> redis.ConnectionPool:
    return redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


def _redis() -> redis.Redis:
    return redis.Redis(connection_pool=_redis_pool())


def _cfg(name: str, default: int) -> int:
    return int(getattr(settings, name, default))


def _fixed_window_allows(key: str, window: int, limit: int) -> bool:
    pipe = _redis().pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    count, _ = pipe.execute()
    return count <= limit


def check_message_rate_limit(user_id: int, chat_id: int) -> bool:
    key = f"aura:ws_msg_rate:{user_id}:{chat_id}"
    try:
        return _fixed_window_allows(
            key,
            _cfg("WS_MESSAGE_RATE_LIMIT_WINDOW", 60),
            _cfg("WS_MESSAGE_RATE_LIMIT_MAX", 10),
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
            key,
            _cfg("WS_TYPING_RATE_LIMIT_WINDOW", 10),
            _cfg("WS_TYPING_RATE_LIMIT_MAX", 20),
        )
    except redis.RedisError:
        logger.warning(
            "Redis error checking typing rate limit, failing open.",
            extra={"user_id": user_id},
        )
        return True


def _ws_connections_key(user_id: int) -> str:
    return f"aura:ws_connections:{user_id}"


def acquire_ws_connection(user_id: int, conn_id: str) -> bool:
    max_conns = _cfg("WS_MAX_CONNECTIONS_PER_USER", 5)
    key = _ws_connections_key(user_id)
    now = time.time()
    try:
        r = _redis()
        pipe = r.pipeline(transaction=True)
        pipe.zremrangebyscore(key, "-inf", now)
        pipe.zadd(key, {conn_id: now + _WS_CONNECTION_TTL})
        pipe.zcard(key)
        pipe.expire(key, _WS_CONNECTION_TTL)
        _, _, count, _ = pipe.execute()
        if count > max_conns:
            r.zrem(key, conn_id)
            return False
        return True
    except redis.RedisError:
        logger.warning(
            "Redis error acquiring WS connection slot, failing open.",
            extra={"user_id": user_id},
        )
        return True


def refresh_ws_connection(user_id: int, conn_id: str) -> None:
    key = _ws_connections_key(user_id)
    try:
        r = _redis()
        r.zadd(key, {conn_id: time.time() + _WS_CONNECTION_TTL}, xx=True)
        r.expire(key, _WS_CONNECTION_TTL)
    except redis.RedisError:
        logger.warning(
            "Redis error refreshing WS connection lease.",
            extra={"user_id": user_id},
        )


def check_artifact_rate_limit(user_id: int, chat_id: int) -> bool:
    key = f"aura:artifact_rate:{user_id}:{chat_id}"
    try:
        return _fixed_window_allows(
            key,
            _cfg("WS_ARTIFACT_RATE_LIMIT_WINDOW", 60),
            _cfg("WS_ARTIFACT_RATE_LIMIT_MAX", 5),
        )
    except redis.RedisError:
        logger.warning(
            "Redis error checking artifact rate limit, failing open.",
            extra={"user_id": user_id, "chat_id": chat_id},
        )
        return True


def check_transcribe_rate_limit(user_id: int) -> bool:
    key = f"aura:transcribe_rate:{user_id}"
    try:
        return _fixed_window_allows(
            key,
            _cfg("WS_TRANSCRIBE_RATE_LIMIT_WINDOW", 60),
            _cfg("WS_TRANSCRIBE_RATE_LIMIT_MAX", 5),
        )
    except redis.RedisError:
        logger.warning(
            "Redis error checking transcription rate limit, failing open.",
            extra={"user_id": user_id},
        )
        return True


def release_ws_connection(user_id: int, conn_id: str) -> None:
    key = _ws_connections_key(user_id)
    try:
        _redis().zrem(key, conn_id)
    except redis.RedisError:
        logger.warning(
            "Redis error releasing WS connection slot.",
            extra={"user_id": user_id},
        )
