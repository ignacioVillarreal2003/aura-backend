import time
import uuid
from typing import Callable
from fastapi import HTTPException, Request, status

_WINDOW_SECONDS = 60


async def _check_rate_limit(request: Request, limit: int) -> None:
    redis_client = getattr(request.app.state, "redis_client", None)
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
        pipe.zadd(key, {str(uuid.uuid4()): now})
        pipe.zcard(key)
        pipe.expire(key, _WINDOW_SECONDS * 2)
        results = await pipe.execute()

    count: int = results[2]
    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry later.",
            headers={"Retry-After": str(_WINDOW_SECONDS)},
        )


def make_rate_limiter(limit: int) -> Callable:
    async def _limiter(request: Request) -> None:
        await _check_rate_limit(request, limit=limit)

    return _limiter


strict_rate_limit = make_rate_limiter(20)
default_rate_limit = make_rate_limiter(60)
