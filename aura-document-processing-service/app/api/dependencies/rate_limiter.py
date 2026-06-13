import math
import time
import uuid
from typing import Callable, Optional
from fastapi import HTTPException, Request, status

from app.infrastructure.persistence.memory_database.redis_client.interfaces.redis_client_interface import (
    RedisClientInterface,
)

_WINDOW_SECONDS = 60
_STRICT_RATE = 20
_DEFAULT_RATE = 60


async def _check_rate_limit(request: Request, limit: int) -> None:
    redis_client: Optional[RedisClientInterface] = getattr(request.app.state, "redis_client", None)
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

    async with redis_client.client.pipeline(transaction=True) as pipe:
        pipe.zremrangebyscore(key, 0, now - _WINDOW_SECONDS)
        pipe.zcard(key)
        pipe.zrange(key, 0, 0, withscores=True)
        results = await pipe.execute()

    count: int = results[1]
    if count >= limit:
        oldest = results[2]
        if oldest:
            oldest_score: float = oldest[0][1]
            retry_after = max(1, math.ceil(oldest_score + _WINDOW_SECONDS - now))
        else:
            retry_after = 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry later.",
            headers={"Retry-After": str(retry_after)},
        )

    async with redis_client.client.pipeline(transaction=True) as pipe:
        pipe.zadd(key, {str(uuid.uuid4()): now})
        pipe.expire(key, _WINDOW_SECONDS * 2)
        await pipe.execute()


def make_rate_limiter(limit: int) -> Callable:
    async def _limiter(request: Request) -> None:
        await _check_rate_limit(request, limit=limit)

    return _limiter


strict_rate_limit = make_rate_limiter(_STRICT_RATE)
default_rate_limit = make_rate_limiter(_DEFAULT_RATE)
