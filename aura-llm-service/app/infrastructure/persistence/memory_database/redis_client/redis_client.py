import asyncio
import logging
from typing import Optional
import redis.asyncio as aioredis
import redis.exceptions as redis_exceptions
from redis.asyncio.connection import ConnectionPool
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

from app.infrastructure.persistence.memory_database.redis_client.redis_client_settings import RedisClientSettings

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(self, redis_client_settings: Optional[RedisClientSettings] = None) -> None:
        self._settings = redis_client_settings or RedisClientSettings()
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[aioredis.Redis] = None
        self._lock = asyncio.Lock()

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RuntimeError(
                "RedisClient has not been initialized. Call initialize() before use."
            )
        return self._client

    async def initialize(self) -> None:
        async with self._lock:
            if self._client is not None:
                logger.debug("Redis client already initialized; skipping.")
                return

            pool = aioredis.ConnectionPool.from_url(
                self._settings.url.get_secret_value(),
                max_connections=self._settings.max_connections,
                socket_connect_timeout=self._settings.socket_connect_timeout,
                socket_timeout=self._settings.socket_timeout,
                socket_keepalive=True,
                health_check_interval=self._settings.health_check_interval,
                retry=Retry(ExponentialBackoff(), self._settings.retry_attempts),
                retry_on_error=[redis_exceptions.ConnectionError, redis_exceptions.TimeoutError],
                decode_responses=True,
            )
            client = aioredis.Redis(connection_pool=pool)

            try:
                await client.ping()
            except Exception:
                await client.aclose()
                await pool.aclose()
                raise

            self._pool = pool
            self._client = client
            logger.info(
                "Redis client initialized.",
                extra={
                    "url": self._redacted_url(),
                    "max_connections": self._settings.max_connections,
                },
            )

    async def dispose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None
        logger.info("Redis client disposed.")

    async def health_check(self) -> bool:
        try:
            await self._ping()
            return True
        except Exception as exc:
            logger.warning("Redis health check failed.", extra={"error": str(exc)})
            return False

    async def _ping(self) -> None:
        if self._client is None:
            raise RuntimeError("Redis client is not initialized.")
        await self._client.ping()

    def _redacted_url(self) -> str:
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(self._settings.url.get_secret_value())
            redacted = parsed._replace(
                netloc=f"{parsed.hostname}:{parsed.port}" if parsed.port else parsed.hostname
            )
            return urlunparse(redacted)
        except Exception:
            return "<unparseable url>"
