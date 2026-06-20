import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from fastapi import HTTPException, Request, status

from app.api.dependencies.rate_limiter_settings import RateLimiterSettings
from app.infrastructure.persistence.memory_database.redis_client.interfaces.redis_client_interface import (
    RedisClientInterface,
)

logger = logging.getLogger(__name__)

_settings = RateLimiterSettings()

_RATE_LIMIT_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]

redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= limit then
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local retry_after = 1
    if oldest[2] then
        retry_after = math.ceil(tonumber(oldest[2]) + window - now)
        if retry_after < 1 then retry_after = 1 end
    end
    return {0, retry_after}
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, math.ceil(window * 2))
return {1, 0}
"""


def _handle_backend_unavailable(reason: str) -> None:
    if _settings.fail_open:
        return
    logger.warning(
        "Rate limiter backend unavailable and fail_open is disabled; rejecting request.",
        extra={"reason": reason},
    )
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Rate limiting is temporarily unavailable. Please retry later.",
        headers={"Retry-After": "1"},
    )


async def _check_rate_limit(request: Request, limit: int) -> None:
    redis_client: RedisClientInterface | None = getattr(request.app.state, "redis_client", None)
    if redis_client is None:
        _handle_backend_unavailable("redis_client_missing")
        return

    auth_user = getattr(request.state, "authenticated_user", None)
    identity = (
        str(auth_user.id)
        if auth_user and hasattr(auth_user, "id")
        else (request.client.host if request.client else "unknown")
    )
    key = f"rl:{identity}:{request.url.path}"
    now = time.time()

    try:
        allowed, retry_after = await redis_client.client.eval(
            _RATE_LIMIT_LUA,
            1,
            key,
            now,
            _settings.window_seconds,
            limit,
            str(uuid.uuid4()),
        )
    except Exception:
        logger.warning("Rate limiter Redis call failed.", exc_info=True)
        _handle_backend_unavailable("redis_eval_error")
        return

    if not int(allowed):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry later.",
            headers={"Retry-After": str(max(1, int(retry_after)))},
        )


def make_rate_limiter(limit: int) -> Callable[[Request], Awaitable[None]]:
    async def _limiter(request: Request) -> None:
        await _check_rate_limit(request, limit=limit)

    return _limiter


strict_rate_limit = make_rate_limiter(_settings.strict_rate)
default_rate_limit = make_rate_limiter(_settings.default_rate)
