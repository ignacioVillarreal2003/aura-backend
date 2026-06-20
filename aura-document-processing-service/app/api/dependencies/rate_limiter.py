import time
import uuid
from collections.abc import Awaitable, Callable
from fastapi import HTTPException, Request, status

from app.infrastructure.persistence.memory_database.redis_client.interfaces.redis_client_interface import (
    RedisClientInterface,
)

_WINDOW_SECONDS = 60
_STRICT_RATE = 20
_DEFAULT_RATE = 60

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


async def _check_rate_limit(request: Request, limit: int) -> None:
    redis_client: RedisClientInterface | None = getattr(request.app.state, "redis_client", None)
    if redis_client is None:
        return

    auth_user = getattr(request.state, "authenticated_user", None)
    identity = (
        str(auth_user.id)
        if auth_user and hasattr(auth_user, "id")
        else (request.client.host if request.client else "unknown")
    )
    key = f"rl:{identity}:{request.url.path}"
    now = time.time()

    allowed, retry_after = await redis_client.client.eval(
        _RATE_LIMIT_LUA,
        1,
        key,
        now,
        _WINDOW_SECONDS,
        limit,
        str(uuid.uuid4()),
    )

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


strict_rate_limit = make_rate_limiter(_STRICT_RATE)
default_rate_limit = make_rate_limiter(_DEFAULT_RATE)
