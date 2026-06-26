import logging
from typing import Optional
import redis.asyncio as aioredis

from app.infrastructure.persistence.memory_database.graph_extraction_lock_store.interfaces.graph_extraction_lock_store_interface import (
    GraphExtractionLockStoreInterface,
)
from app.infrastructure.persistence.memory_database.redis_client.redis_client_settings import RedisClientSettings

logger = logging.getLogger(__name__)

_RELEASE_IF_OWNER_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


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

    def _lock_key(self, document_id: int) -> str:
        return f"{self._prefix}:lock:{document_id}"

    async def try_acquire_extraction_lock(
            self,
            *,
            document_id: int,
            job_id: str,
    ) -> bool:
        ok = await self._redis.set(
            self._lock_key(document_id),
            job_id,
            nx=True,
            ex=self._lock_ttl_seconds,
        )
        return bool(ok)

    async def release_extraction_lock(
            self,
            *,
            document_id: int,
            job_id: Optional[str] = None,
    ) -> None:
        if job_id is None:
            await self._redis.delete(self._lock_key(document_id))
        else:
            await self._redis.eval(_RELEASE_IF_OWNER_SCRIPT, 1, self._lock_key(document_id), job_id)  # type: ignore[misc]
