import asyncio
import logging
from typing import Optional
import redis.asyncio as aioredis

from app.infrastructure.persistence.memory_database.graph_extraction_lock_store.interfaces.graph_extraction_lock_store_interface import (
    GraphExtractionLockStoreInterface,
)
from app.infrastructure.persistence.memory_database.redis_client.redis_client_settings import RedisClientSettings
from app.infrastructure.persistence.memory_database.redis_lock import (
    release_if_owner,
    start_lock_refresher,
    stop_lock_refresher,
)

logger = logging.getLogger(__name__)


class GraphExtractionLockStore(GraphExtractionLockStoreInterface):
    def __init__(
            self,
            redis_client: aioredis.Redis,
            settings: Optional[RedisClientSettings] = None,
            *,
            lock_ttl_seconds: int = 1800,
    ) -> None:
        self._redis = redis_client
        self._settings = settings or RedisClientSettings()
        self._lock_ttl_seconds = max(60, int(lock_ttl_seconds))
        self._prefix = f"{self._settings.key_prefix}:kg:extraction"
        self._refreshers: dict[int, asyncio.Task] = {}

    def _lock_key(self, document_id: int) -> str:
        return f"{self._prefix}:lock:{document_id}"

    async def try_acquire_extraction_lock(
            self,
            *,
            document_id: int,
            job_id: str,
    ) -> bool:
        acquired = bool(
            await self._redis.set(
                self._lock_key(document_id),
                job_id,
                nx=True,
                ex=self._lock_ttl_seconds,
            )
        )
        if acquired:
            self._refreshers[document_id] = start_lock_refresher(
                self._redis,
                key=self._lock_key(document_id),
                token=job_id,
                ttl_seconds=self._lock_ttl_seconds,
            )
        return acquired

    async def release_extraction_lock(
            self,
            *,
            document_id: int,
            job_id: Optional[str] = None,
    ) -> None:
        await stop_lock_refresher(self._refreshers.pop(document_id, None))
        if job_id is None:
            await self._redis.delete(self._lock_key(document_id))
        else:
            await release_if_owner(self._redis, key=self._lock_key(document_id), token=job_id)
