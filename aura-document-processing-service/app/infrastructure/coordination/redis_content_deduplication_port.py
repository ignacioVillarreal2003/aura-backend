import logging
from typing import Optional

import redis.asyncio as redis

from app.application.coordination.interfaces.content_deduplication_port_interface import (
    ContentDeduplicationPortInterface,
)
from app.infrastructure.coordination.redis_coordination_settings import RedisCoordinationSettings

logger = logging.getLogger(__name__)


class RedisContentDeduplicationPort(ContentDeduplicationPortInterface):
    def __init__(
            self,
            redis_client: redis.Redis,
            settings: Optional[RedisCoordinationSettings] = None,
    ) -> None:
        self._redis = redis_client
        self._settings = settings or RedisCoordinationSettings()

    def _key(
            self,
            file_hash: str,
    ) -> str:
        return f"{self._settings.key_prefix}:content_dedup:{file_hash}"

    async def try_claim_content_hash(
            self,
            file_hash: str,
            window_seconds: int,
    ) -> bool:
        if not file_hash:
            return False
        acquired = await self._redis.set(
            self._key(file_hash),
            "1",
            nx=True,
            ex=max(1, int(window_seconds)),
        )
        return bool(acquired)

    async def release_content_hash_claim(
            self,
            file_hash: str,
    ) -> None:
        if not file_hash:
            return
        await self._redis.delete(self._key(file_hash))
