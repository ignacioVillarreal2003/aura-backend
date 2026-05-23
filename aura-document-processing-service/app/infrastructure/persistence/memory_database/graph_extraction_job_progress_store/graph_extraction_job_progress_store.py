import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
import redis.asyncio as aioredis

from app.domain.dtos.graph.graph_field_limits import MAX_KNOWLEDGE_GRAPH_ERRORS
from app.infrastructure.persistence.memory_database.graph_extraction_job_progress_store.graph_extraction_job_progress_store_interface import (
    GraphExtractionJobProgressStoreInterface,
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

_MARK_PROGRESS_SCRIPT = """
local raw = redis.call("GET", KEYS[1])
if not raw then return 0 end
local snap = cjson.decode(raw)
if snap["job_id"] ~= ARGV[1] then return 0 end
if ARGV[2] ~= "" then snap["current_fragment_id"] = tonumber(ARGV[2]) end
snap["processed_fragments"]  = (snap["processed_fragments"]  or 0) + tonumber(ARGV[3])
snap["failed_fragments"]     = (snap["failed_fragments"]     or 0) + tonumber(ARGV[4])
snap["extracted_entities"]   = (snap["extracted_entities"]   or 0) + tonumber(ARGV[5])
snap["extracted_relations"]  = (snap["extracted_relations"]  or 0) + tonumber(ARGV[6])
redis.call("SET", KEYS[1], cjson.encode(snap), "EX", tonumber(ARGV[7]))
return 1
"""

_APPEND_ERROR_SCRIPT = """
local raw = redis.call("GET", KEYS[1])
if not raw then return 0 end
local snap = cjson.decode(raw)
if snap["job_id"] ~= ARGV[1] then return 0 end
local errors = snap["errors"] or {}
if #errors >= tonumber(ARGV[2]) then return 0 end
table.insert(errors, cjson.decode(ARGV[3]))
snap["errors"] = errors
redis.call("SET", KEYS[1], cjson.encode(snap), "EX", tonumber(ARGV[4]))
return 1
"""


class GraphExtractionJobProgressStore(GraphExtractionJobProgressStoreInterface):
    def __init__(
            self,
            redis_client: aioredis.Redis,
            settings: Optional[RedisClientSettings] = None,
            *,
            lock_ttl_seconds: int = 1800,
            snapshot_ttl_seconds: int = 86_400,
    ) -> None:
        self._redis = redis_client
        self._settings = settings or RedisClientSettings()
        self._lock_ttl_seconds = max(60, int(lock_ttl_seconds))
        self._snapshot_ttl_seconds = max(60, int(snapshot_ttl_seconds))
        self._prefix = f"{self._settings.key_prefix}:kg:extraction"

    def _lock_key(self, document_id: int) -> str:
        return f"{self._prefix}:lock:{document_id}"

    def _snapshot_key(self, document_id: int) -> str:
        return f"{self._prefix}:snapshot:{document_id}"

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
            await self._redis.eval(_RELEASE_IF_OWNER_SCRIPT, 1, self._lock_key(document_id), job_id)

    async def begin_job(
            self,
            *,
            job_id: str,
            document_id: int,
            total_fragments: int,
    ) -> None:
        snapshot = {
            "job_id": job_id,
            "document_id": document_id,
            "is_running": True,
            "total_fragments": int(total_fragments),
            "processed_fragments": 0,
            "failed_fragments": 0,
            "extracted_entities": 0,
            "extracted_relations": 0,
            "current_fragment_id": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "errors": [],
        }
        await self._redis.set(
            self._snapshot_key(document_id),
            json.dumps(snapshot),
            ex=self._snapshot_ttl_seconds,
        )

    async def mark_progress(
            self,
            *,
            job_id: str,
            document_id: int,
            current_fragment_id: Optional[int] = None,
            processed_increment: int = 0,
            failed_increment: int = 0,
            extracted_entities_increment: int = 0,
            extracted_relations_increment: int = 0,
    ) -> None:
        fragment_id_arg = str(current_fragment_id) if current_fragment_id is not None else ""
        await self._redis.eval(
            _MARK_PROGRESS_SCRIPT,
            1,
            self._snapshot_key(document_id),
            job_id,
            fragment_id_arg,
            str(processed_increment),
            str(failed_increment),
            str(extracted_entities_increment),
            str(extracted_relations_increment),
            str(self._snapshot_ttl_seconds),
        )

    async def append_error(
            self,
            *,
            job_id: str,
            document_id: int,
            error: dict[str, Any],
    ) -> None:
        await self._redis.eval(
            _APPEND_ERROR_SCRIPT,
            1,
            self._snapshot_key(document_id),
            job_id,
            str(MAX_KNOWLEDGE_GRAPH_ERRORS),
            json.dumps(error),
            str(self._snapshot_ttl_seconds),
        )

    async def complete_job(
            self,
            *,
            job_id: str,
            document_id: int,
    ) -> None:
        snapshot = await self._get_snapshot(document_id)
        if snapshot is not None and snapshot.get("job_id") == job_id:
            snapshot["is_running"] = False
            snapshot["current_fragment_id"] = None
            snapshot["finished_at"] = datetime.now(timezone.utc).isoformat()
            await self._redis.set(
                self._snapshot_key(document_id),
                json.dumps(snapshot),
                ex=self._snapshot_ttl_seconds,
            )

    async def get_snapshot(
            self,
            *,
            document_id: int,
    ) -> Optional[dict[str, Any]]:
        return await self._get_snapshot(document_id)

    async def _get_snapshot(
            self,
            document_id: int,
    ) -> Optional[dict[str, Any]]:
        raw = await self._redis.get(self._snapshot_key(document_id))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error(
                "Knowledge graph extraction snapshot value was not valid JSON.",
                extra={"document_id": document_id},
            )
            return None
        return data if isinstance(data, dict) else None
