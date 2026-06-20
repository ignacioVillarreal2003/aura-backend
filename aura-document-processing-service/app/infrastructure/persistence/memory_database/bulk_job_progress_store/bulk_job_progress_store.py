import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
import redis.asyncio as aioredis

from app.domain.constants.document.bulk_operation import BulkOperation
from app.domain.field_limits import MAX_POST_PROCESS_SNAPSHOT_ERRORS
from app.infrastructure.persistence.memory_database.bulk_job_progress_store.interfaces.bulk_job_progress_store_interface import (
    BulkJobProgressStoreInterface,
)
from app.infrastructure.persistence.memory_database.redis_client.redis_client_settings import RedisClientSettings

logger = logging.getLogger(__name__)

_MARK_SCRIPT = """
local raw = redis.call("GET", KEYS[1])
if not raw then return 0 end
local snap = cjson.decode(raw)
if snap["job_id"] ~= ARGV[1] then return 0 end
snap["processed"] = (snap["processed"] or 0) + tonumber(ARGV[2])
snap["failed"] = (snap["failed"] or 0) + tonumber(ARGV[3])
snap["heartbeat_at"] = ARGV[4]
if (snap["processed"] + snap["failed"]) >= (snap["total"] or 0) then
    snap["is_running"] = false
    if not snap["finished_at"] or snap["finished_at"] == cjson.null then
        snap["finished_at"] = ARGV[4]
    end
end
redis.call("SET", KEYS[1], cjson.encode(snap), "EX", tonumber(ARGV[5]))
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

_REQUEST_STOP_SCRIPT = """
local raw = redis.call("GET", KEYS[1])
if not raw then return 0 end
local snap = cjson.decode(raw)
snap["stop_requested"] = true
redis.call("SET", KEYS[1], cjson.encode(snap), "EX", tonumber(ARGV[1]))
return 1
"""


class BulkJobProgressStore(BulkJobProgressStoreInterface):
    def __init__(
            self,
            redis_client: aioredis.Redis,
            settings: Optional[RedisClientSettings] = None,
            *,
            snapshot_ttl_seconds: int = 86_400,
    ) -> None:
        self._redis = redis_client
        self._settings = settings or RedisClientSettings()
        self._snapshot_ttl_seconds = max(60, int(snapshot_ttl_seconds))
        self._prefix = f"{self._settings.key_prefix}:bulk"

    def _snapshot_key(self, operation: BulkOperation) -> str:
        return f"{self._prefix}:{operation.value}:snapshot"

    async def begin_job(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
            total: int,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        snapshot = {
            "job_id": job_id,
            "operation": operation.value,
            "is_running": True,
            "stop_requested": False,
            "total": int(total),
            "processed": 0,
            "failed": 0,
            "started_at": now_iso,
            "heartbeat_at": now_iso,
            "finished_at": None,
            "errors": [],
        }
        await self._redis.set(
            self._snapshot_key(operation),
            json.dumps(snapshot),
            ex=self._snapshot_ttl_seconds,
        )

    async def mark(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
            processed_increment: int = 0,
            failed_increment: int = 0,
    ) -> None:
        await self._redis.eval(  # type: ignore[misc]
            _MARK_SCRIPT,
            1,
            self._snapshot_key(operation),
            job_id,
            str(int(processed_increment)),
            str(int(failed_increment)),
            datetime.now(timezone.utc).isoformat(),
            str(self._snapshot_ttl_seconds),
        )

    async def append_error(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
            error: dict[str, Any],
    ) -> None:
        await self._redis.eval(  # type: ignore[misc]
            _APPEND_ERROR_SCRIPT,
            1,
            self._snapshot_key(operation),
            job_id,
            str(MAX_POST_PROCESS_SNAPSHOT_ERRORS),
            json.dumps(error),
            str(self._snapshot_ttl_seconds),
        )

    async def request_stop(
            self,
            *,
            operation: BulkOperation,
    ) -> bool:
        result = await self._redis.eval(  # type: ignore[misc]
            _REQUEST_STOP_SCRIPT,
            1,
            self._snapshot_key(operation),
            str(self._snapshot_ttl_seconds),
        )
        return bool(result)

    async def is_stopped(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
    ) -> bool:
        snapshot = await self.get_snapshot(operation=operation)
        if snapshot is None or snapshot.get("job_id") != job_id:
            return False
        return bool(snapshot.get("stop_requested"))

    async def get_snapshot(
            self,
            *,
            operation: BulkOperation,
    ) -> Optional[dict[str, Any]]:
        raw = await self._redis.get(self._snapshot_key(operation))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error(
                "Bulk job snapshot value was not valid JSON.",
                extra={"operation": operation.value},
            )
            return None
        if not isinstance(data, dict):
            return None
        if not isinstance(data.get("errors"), list):
            data["errors"] = []
        return data
