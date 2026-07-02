import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

_REFRESH_IF_OWNER_SCRIPT = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('pexpire', KEYS[1], ARGV[2]) "
    "else return 0 end"
)

RELEASE_IF_OWNER_SCRIPT = (
    "if redis.call('get', KEYS[1]) == ARGV[1] "
    "then return redis.call('del', KEYS[1]) "
    "else return 0 end"
)


def _refresh_interval_seconds(ttl_seconds: int) -> int:
    return max(1, int(ttl_seconds) // 3)


async def _refresh_loop(
        redis: aioredis.Redis,
        key: str,
        token: str,
        ttl_seconds: int,
) -> None:
    interval = _refresh_interval_seconds(ttl_seconds)
    ttl_ms = str(int(ttl_seconds) * 1000)
    while True:
        await asyncio.sleep(interval)
        try:
            await redis.eval(_REFRESH_IF_OWNER_SCRIPT, 1, key, token, ttl_ms)  # type: ignore[misc]
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.warning(
                "Failed to refresh a distributed lock; it may expire if the outage persists.",
                extra={"lock_key": key},
                exc_info=True,
            )


def start_lock_refresher(
        redis: aioredis.Redis,
        *,
        key: str,
        token: str,
        ttl_seconds: int,
) -> asyncio.Task:
    return asyncio.create_task(_refresh_loop(redis, key, token, ttl_seconds))


async def stop_lock_refresher(task: Optional[asyncio.Task]) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def release_if_owner(
        redis: aioredis.Redis,
        *,
        key: str,
        token: str,
) -> None:
    try:
        await redis.eval(RELEASE_IF_OWNER_SCRIPT, 1, key, token)  # type: ignore[misc]
    except Exception:
        logger.warning(
            "Failed to release a distributed lock; it will expire on its TTL.",
            extra={"lock_key": key},
            exc_info=True,
        )


@asynccontextmanager
async def refreshing_redis_lock(
        redis: aioredis.Redis,
        *,
        key: str,
        token: str,
        ttl_seconds: int,
) -> AsyncIterator[bool]:
    acquired = bool(await redis.set(key, token, nx=True, ex=ttl_seconds))
    refresher: Optional[asyncio.Task] = None
    if acquired:
        refresher = start_lock_refresher(redis, key=key, token=token, ttl_seconds=ttl_seconds)
    try:
        yield acquired
    finally:
        await stop_lock_refresher(refresher)
        if acquired:
            await release_if_owner(redis, key=key, token=token)
