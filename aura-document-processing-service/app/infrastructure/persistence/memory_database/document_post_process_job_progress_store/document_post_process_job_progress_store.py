import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
import redis.asyncio as aioredis

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.field_limits import MAX_POST_PROCESS_SNAPSHOT_ERRORS
from app.infrastructure.persistence.memory_database.document_post_process_job_progress_store.document_post_process_job_progress_store_interface import (
    DocumentPostProcessJobProgressStoreInterface,
)
from app.infrastructure.persistence.memory_database.redis_client.redis_client_settings import RedisClientSettings

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DocumentPostProcessJobProgressStore(DocumentPostProcessJobProgressStoreInterface):
    def __init__(
            self,
            redis_client: aioredis.Redis,
            settings: Optional[RedisClientSettings] = None,
    ) -> None:
        self._redis = redis_client
        self._settings = settings or RedisClientSettings()
        p = self._settings.key_prefix
        self._snapshot_key = f"{p}:post_process:document:snapshot"
        self._lock_key = f"{p}:post_process:document:lock"

    def _manifest_key(self, job_id: str) -> str:
        return f"{self._settings.key_prefix}:post_process:document:manifest:{job_id}"

    async def try_begin_document_job(
            self,
            *,
            job_id: str,
            total_documents: int,
            document_ids: list[int],
            triggered_by: AuthenticatedUser,
    ) -> bool:
        lock_ok = await self._redis.set(
            self._lock_key,
            job_id,
            nx=True,
            ex=self._settings.post_process_job_lock_ttl_seconds,
        )
        if not lock_ok:
            return False

        try:
            ttl = self._settings.post_process_job_lock_ttl_seconds
            manifest = {
                "job_id": job_id,
                "document_ids": document_ids,
                "user": triggered_by.model_dump(mode="json"),
            }
            snapshot = {
                "job_id": job_id,
                "is_running": True,
                "stop_requested": False,
                "total_documents": total_documents,
                "processed_documents": 0,
                "failed_documents": 0,
                "current_document_id": None,
                "started_at": _utc_now_iso(),
                "finished_at": None,
                "errors": [],
            }
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.set(self._manifest_key(job_id), json.dumps(manifest), ex=ttl)
                pipe.set(self._snapshot_key, json.dumps(snapshot), ex=ttl)
                await pipe.execute()
            return True
        except Exception:
            await self._redis.delete(self._lock_key)
            raise

    async def abort_document_job(self, job_id: str) -> None:
        await self._redis.delete(self._manifest_key(job_id))
        snap = await self._get_json(self._snapshot_key)
        if snap and snap.get("job_id") == job_id:
            snap["is_running"] = False
            snap["finished_at"] = _utc_now_iso()
            await self._redis.set(self._snapshot_key, json.dumps(snap))
        await self._redis.delete(self._lock_key)

    async def get_document_job_snapshot(self) -> Optional[dict[str, Any]]:
        return await self._get_json(self._snapshot_key)

    async def get_document_job_manifest(self, job_id: str) -> Optional[dict[str, Any]]:
        return await self._get_json(self._manifest_key(job_id))

    async def request_document_stop(self) -> None:
        snap = await self._get_json(self._snapshot_key)
        if not snap:
            return
        snap["stop_requested"] = True
        await self._redis.set(self._snapshot_key, json.dumps(snap))

    async def mark_document_job_progress(
            self,
            job_id: str,
            *,
            current_document_id: Optional[int] = None,
            processed_increment: int = 0,
            failed_increment: int = 0,
    ) -> None:
        snap = await self._get_json(self._snapshot_key)
        if not snap or snap.get("job_id") != job_id:
            return
        if current_document_id is not None:
            snap["current_document_id"] = current_document_id
        snap["processed_documents"] = int(snap.get("processed_documents", 0)) + processed_increment
        snap["failed_documents"] = int(snap.get("failed_documents", 0)) + failed_increment
        await self._redis.set(self._snapshot_key, json.dumps(snap))

    async def append_document_job_error(self, job_id: str, error: dict[str, Any]) -> None:
        snap = await self._get_json(self._snapshot_key)
        if not snap or snap.get("job_id") != job_id:
            return
        errors = list(snap.get("errors") or [])
        if len(errors) >= MAX_POST_PROCESS_SNAPSHOT_ERRORS:
            return
        errors.append(error)
        snap["errors"] = errors
        await self._redis.set(self._snapshot_key, json.dumps(snap))

    async def complete_document_job(self, job_id: str) -> None:
        await self._redis.delete(self._manifest_key(job_id))
        snap = await self._get_json(self._snapshot_key)
        if snap and snap.get("job_id") == job_id:
            snap["is_running"] = False
            snap["current_document_id"] = None
            snap["finished_at"] = _utc_now_iso()
            snap["stop_requested"] = False
            await self._redis.set(self._snapshot_key, json.dumps(snap))
        await self._redis.delete(self._lock_key)

    async def is_document_stop_requested(self, job_id: str) -> bool:
        snap = await self._get_json(self._snapshot_key)
        if not snap or snap.get("job_id") != job_id:
            return False
        return bool(snap.get("stop_requested"))

    async def _get_json(self, key: str) -> Optional[dict[str, Any]]:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Redis value was not valid JSON.", extra={"redis_key": key})
            return None
        return data if isinstance(data, dict) else None
