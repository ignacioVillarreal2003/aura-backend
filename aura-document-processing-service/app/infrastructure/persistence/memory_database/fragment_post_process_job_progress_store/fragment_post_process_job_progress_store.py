import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as aioredis

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.field_limits import MAX_POST_PROCESS_SNAPSHOT_ERRORS
from app.infrastructure.persistence.memory_database.fragment_post_process_job_progress_store.fragment_post_process_job_progress_store_interface import (
    FragmentPostProcessJobProgressStoreInterface,
)
from app.infrastructure.persistence.memory_database.redis_client.redis_client_settings import RedisClientSettings

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FragmentPostProcessJobProgressStore(FragmentPostProcessJobProgressStoreInterface):
    def __init__(
            self,
            redis_client: aioredis.Redis,
            settings: Optional[RedisClientSettings] = None,
    ) -> None:
        self._redis = redis_client
        self._settings = settings or RedisClientSettings()
        p = self._settings.key_prefix
        self._snapshot_key = f"{p}:post_process:fragment:snapshot"
        self._lock_key = f"{p}:post_process:fragment:lock"

    def _manifest_key(self, job_id: str) -> str:
        return f"{self._settings.key_prefix}:post_process:fragment:manifest:{job_id}"

    async def try_begin_fragment_job(
            self,
            *,
            job_id: str,
            total_fragments: int,
            document_ids: Optional[list[int]],
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
                "total_fragments": total_fragments,
                "last_fragment_id": None,
                "user": triggered_by.model_dump(mode="json"),
            }
            snapshot = {
                "job_id": job_id,
                "is_running": True,
                "stop_requested": False,
                "total_fragments": total_fragments,
                "processed_fragments": 0,
                "failed_fragments": 0,
                "current_fragment_id": None,
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

    async def abort_fragment_job(self, job_id: str) -> None:
        await self._redis.delete(self._manifest_key(job_id))
        snap = await self._get_json(self._snapshot_key)
        if snap and snap.get("job_id") == job_id:
            snap["is_running"] = False
            snap["finished_at"] = _utc_now_iso()
            await self._redis.set(self._snapshot_key, json.dumps(snap))
        await self._redis.delete(self._lock_key)

    async def get_fragment_job_snapshot(self) -> Optional[dict[str, Any]]:
        return await self._get_json(self._snapshot_key)

    async def get_fragment_job_manifest(self, job_id: str) -> Optional[dict[str, Any]]:
        return await self._get_json(self._manifest_key(job_id))

    async def request_fragment_stop(self) -> None:
        snap = await self._get_json(self._snapshot_key)
        if not snap:
            return
        snap["stop_requested"] = True
        await self._redis.set(self._snapshot_key, json.dumps(snap))

    async def mark_fragment_job_progress(
            self,
            job_id: str,
            *,
            current_fragment_id: Optional[int] = None,
            processed_increment: int = 0,
            failed_increment: int = 0,
    ) -> None:
        snap = await self._get_json(self._snapshot_key)
        if not snap or snap.get("job_id") != job_id:
            return
        if current_fragment_id is not None:
            snap["current_fragment_id"] = current_fragment_id
        snap["processed_fragments"] = int(snap.get("processed_fragments", 0)) + processed_increment
        snap["failed_fragments"] = int(snap.get("failed_fragments", 0)) + failed_increment
        await self._redis.set(self._snapshot_key, json.dumps(snap))

    async def append_fragment_job_error(self, job_id: str, error: dict[str, Any]) -> None:
        snap = await self._get_json(self._snapshot_key)
        if not snap or snap.get("job_id") != job_id:
            return
        errors = list(snap.get("errors") or [])
        if len(errors) >= MAX_POST_PROCESS_SNAPSHOT_ERRORS:
            return
        errors.append(error)
        snap["errors"] = errors
        await self._redis.set(self._snapshot_key, json.dumps(snap))

    async def complete_fragment_job(self, job_id: str) -> None:
        await self._redis.delete(self._manifest_key(job_id))
        snap = await self._get_json(self._snapshot_key)
        if snap and snap.get("job_id") == job_id:
            snap["is_running"] = False
            snap["current_fragment_id"] = None
            snap["finished_at"] = _utc_now_iso()
            snap["stop_requested"] = False
            await self._redis.set(self._snapshot_key, json.dumps(snap))
        await self._redis.delete(self._lock_key)

    async def is_fragment_stop_requested(self, job_id: str) -> bool:
        snap = await self._get_json(self._snapshot_key)
        if not snap or snap.get("job_id") != job_id:
            return False
        return bool(snap.get("stop_requested"))

    async def update_fragment_job_cursor(
            self,
            job_id: str,
            last_fragment_id: Optional[int],
    ) -> None:
        key = self._manifest_key(job_id)
        raw = await self._redis.get(key)
        if not raw:
            return
        try:
            manifest = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Fragment job manifest was not valid JSON; skipping cursor update.", extra={"job_id": job_id})
            return
        manifest["last_fragment_id"] = last_fragment_id
        await self._redis.set(key, json.dumps(manifest), ex=self._settings.post_process_job_lock_ttl_seconds)

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
