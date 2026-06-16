import logging
import math
import time
import uuid
from typing import Callable
import redis.exceptions as redis_exceptions
from fastapi import HTTPException, Request, status

from app.configuration.environment_variables import get_settings

logger = logging.getLogger(__name__)

_RATE_LIMIT_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
local ttl = tonumber(ARGV[5])

redis.call('zremrangebyscore', key, 0, now - window)
local count = redis.call('zcard', key)
if count >= limit then
    local oldest = redis.call('zrange', key, 0, 0, 'WITHSCORES')
    return {0, oldest[2] or '0'}
end
redis.call('zadd', key, now, member)
redis.call('expire', key, ttl)
return {1, '0'}
"""


async def _check_rate_limit(request: Request, limit: int) -> None:
    redis_client = getattr(request.app.state, "redis_client", None)
    if redis_client is None:
        return

    window_seconds = get_settings().rate_limit_window_seconds

    auth_user = getattr(request.state, "authenticated_user", None)
    identity = (
        str(auth_user.id)
        if auth_user and hasattr(auth_user, "id")
        else (request.client.host if request.client else "unknown")
    )
    key = f"rl:{identity}:{request.url.path}"
    now = time.time()

    try:
        allowed, oldest_score = await redis_client.client.eval(
            _RATE_LIMIT_SCRIPT,
            1,
            key,
            now,
            window_seconds,
            limit,
            str(uuid.uuid4()),
            window_seconds * 2,
        )
    except (redis_exceptions.RedisError, OSError):
        logger.warning(
            "Rate limit check failed; allowing request (fail-open).",
            extra={"path": request.url.path},
            exc_info=True,
        )
        return

    if int(allowed) == 1:
        return

    try:
        oldest = float(oldest_score)
    except (TypeError, ValueError):
        oldest = now
    retry_after = max(1, math.ceil(oldest + window_seconds - now))
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded. Please retry later.",
        headers={"Retry-After": str(retry_after)},
    )


def make_rate_limiter(kind: str) -> Callable:
    """Build a FastAPI dependency that enforces the ``kind`` ("strict"/"default")
    rate limit. The numeric limit and window are read from settings per-request
    (not bound at import time), so configuration stays overridable in tests."""

    async def _limiter(request: Request) -> None:
        settings = get_settings()
        limit = (
            settings.rate_limit_strict_per_window
            if kind == "strict"
            else settings.rate_limit_default_per_window
        )
        await _check_rate_limit(request, limit=limit)

    return _limiter


strict_rate_limit = make_rate_limiter("strict")
default_rate_limit = make_rate_limiter("default")
