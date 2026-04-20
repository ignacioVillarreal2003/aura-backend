import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import redis.asyncio as redis

from app.application.coordination.interfaces.post_process_job_progress_store_interface import (
    PostProcessJobProgressStoreInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.coordination.redis_coordination_settings import RedisCoordinationSettings

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RedisPostProcessJobProgressStore(PostProcessJobProgressStoreInterface):
    def __init__(
            self,
            redis_client: redis.Redis,
            settings: Optional[RedisCoordinationSettings] = None,
    ) -> None:
        self._redis = redis_client
        self._settings = settings or RedisCoordinationSettings()
        p = self._settings.key_prefix
        self._doc_snapshot_key = f"{p}:post_process:document:snapshot"
        self._doc_lock_key = f"{p}:post_process:document:lock"
        self._frag_snapshot_key = f"{p}:post_process:fragment:snapshot"
        self._frag_lock_key = f"{p}:post_process:fragment:lock"

    def _doc_manifest_key(
            self,
            job_id: str,
    ) -> str:
        return f"{self._settings.key_prefix}:post_process:document:manifest:{job_id}"

    def _frag_manifest_key(
            self,
            job_id: str,
    ) -> str:
        return f"{self._settings.key_prefix}:post_process:fragment:manifest:{job_id}"

    async def try_begin_document_job(
            self,
            *,
            job_id: str,
            total_documents: int,
            document_ids: list[int],
            triggered_by: AuthenticatedUser,
    ) -> bool:
        lock_ok = await self._redis.set(
            self._doc_lock_key,
            job_id,
            nx=True,
            ex=self._settings.post_process_job_lock_ttl_seconds,
        )
        if not lock_ok:
            snap = await self._get_json(self._doc_snapshot_key)
            if snap and snap.get("is_running"):
                return False
            return False

        try:
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
            await self._redis.set(self._doc_manifest_key(job_id), json.dumps(manifest))
            await self._redis.set(self._doc_snapshot_key, json.dumps(snapshot))
            return True
        except Exception:
            await self._redis.delete(self._doc_lock_key)
            raise

    async def abort_document_job(
            self,
            job_id: str,
    ) -> None:
        await self._redis.delete(self._doc_manifest_key(job_id))
        snap = await self._get_json(self._doc_snapshot_key)
        if snap and snap.get("job_id") == job_id:
            snap["is_running"] = False
            snap["finished_at"] = _utc_now_iso()
            await self._redis.set(self._doc_snapshot_key, json.dumps(snap))
        await self._redis.delete(self._doc_lock_key)

    async def get_document_job_snapshot(
            self,
    ) -> Optional[dict[str, Any]]:
        return await self._get_json(self._doc_snapshot_key)

    async def request_document_stop(
            self,
    ) -> None:
        snap = await self._get_json(self._doc_snapshot_key)
        if not snap:
            return
        snap["stop_requested"] = True
        await self._redis.set(self._doc_snapshot_key, json.dumps(snap))

    async def get_document_job_manifest(
            self,
            job_id: str,
    ) -> Optional[dict[str, Any]]:
        return await self._get_json(self._doc_manifest_key(job_id))

    async def mark_document_job_progress(
            self,
            job_id: str,
            *,
            current_document_id: Optional[int] = None,
            processed_increment: int = 0,
            failed_increment: int = 0,
    ) -> None:
        snap = await self._get_json(self._doc_snapshot_key)
        if not snap or snap.get("job_id") != job_id:
            return
        if current_document_id is not None:
            snap["current_document_id"] = current_document_id
        snap["processed_documents"] = int(snap.get("processed_documents", 0)) + processed_increment
        snap["failed_documents"] = int(snap.get("failed_documents", 0)) + failed_increment
        await self._redis.set(self._doc_snapshot_key, json.dumps(snap))

    async def append_document_job_error(
            self,
            job_id: str,
            error: dict[str, Any],
    ) -> None:
        snap = await self._get_json(self._doc_snapshot_key)
        if not snap or snap.get("job_id") != job_id:
            return
        errors = list(snap.get("errors") or [])
        errors.append(error)
        snap["errors"] = errors
        await self._redis.set(self._doc_snapshot_key, json.dumps(snap))

    async def complete_document_job(
            self,
            job_id: str,
    ) -> None:
        await self._redis.delete(self._doc_manifest_key(job_id))
        snap = await self._get_json(self._doc_snapshot_key)
        if snap and snap.get("job_id") == job_id:
            snap["is_running"] = False
            snap["current_document_id"] = None
            snap["finished_at"] = _utc_now_iso()
            snap["stop_requested"] = False
            await self._redis.set(self._doc_snapshot_key, json.dumps(snap))
        await self._redis.delete(self._doc_lock_key)

    async def is_document_stop_requested(
            self,
            job_id: str,
    ) -> bool:
        snap = await self._get_json(self._doc_snapshot_key)
        if not snap or snap.get("job_id") != job_id:
            return False
        return bool(snap.get("stop_requested"))

    async def try_begin_fragment_job(
            self,
            *,
            job_id: str,
            total_fragments: int,
            document_ids: Optional[list[int]],
            triggered_by: AuthenticatedUser,
    ) -> bool:
        lock_ok = await self._redis.set(
            self._frag_lock_key,
            job_id,
            nx=True,
            ex=self._settings.post_process_job_lock_ttl_seconds,
        )
        if not lock_ok:
            snap = await self._get_json(self._frag_snapshot_key)
            if snap and snap.get("is_running"):
                return False
            return False

        try:
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
            await self._redis.set(self._frag_manifest_key(job_id), json.dumps(manifest))
            await self._redis.set(self._frag_snapshot_key, json.dumps(snapshot))
            return True
        except Exception:
            await self._redis.delete(self._frag_lock_key)
            raise

    async def abort_fragment_job(
            self,
            job_id: str,
    ) -> None:
        await self._redis.delete(self._frag_manifest_key(job_id))
        snap = await self._get_json(self._frag_snapshot_key)
        if snap and snap.get("job_id") == job_id:
            snap["is_running"] = False
            snap["finished_at"] = _utc_now_iso()
            await self._redis.set(self._frag_snapshot_key, json.dumps(snap))
        await self._redis.delete(self._frag_lock_key)

    async def get_fragment_job_snapshot(
            self,
    ) -> Optional[dict[str, Any]]:
        return await self._get_json(self._frag_snapshot_key)

    async def request_fragment_stop(
            self,
    ) -> None:
        snap = await self._get_json(self._frag_snapshot_key)
        if not snap:
            return
        snap["stop_requested"] = True
        await self._redis.set(self._frag_snapshot_key, json.dumps(snap))

    async def get_fragment_job_manifest(
            self,
            job_id: str,
    ) -> Optional[dict[str, Any]]:
        return await self._get_json(self._frag_manifest_key(job_id))

    async def mark_fragment_job_progress(
            self,
            job_id: str,
            *,
            current_fragment_id: Optional[int] = None,
            processed_increment: int = 0,
            failed_increment: int = 0,
    ) -> None:
        snap = await self._get_json(self._frag_snapshot_key)
        if not snap or snap.get("job_id") != job_id:
            return
        if current_fragment_id is not None:
            snap["current_fragment_id"] = current_fragment_id
        snap["processed_fragments"] = int(snap.get("processed_fragments", 0)) + processed_increment
        snap["failed_fragments"] = int(snap.get("failed_fragments", 0)) + failed_increment
        await self._redis.set(self._frag_snapshot_key, json.dumps(snap))

    async def append_fragment_job_error(
            self,
            job_id: str,
            error: dict[str, Any],
    ) -> None:
        snap = await self._get_json(self._frag_snapshot_key)
        if not snap or snap.get("job_id") != job_id:
            return
        errors = list(snap.get("errors") or [])
        errors.append(error)
        snap["errors"] = errors
        await self._redis.set(self._frag_snapshot_key, json.dumps(snap))

    async def complete_fragment_job(
            self,
            job_id: str,
    ) -> None:
        await self._redis.delete(self._frag_manifest_key(job_id))
        snap = await self._get_json(self._frag_snapshot_key)
        if snap and snap.get("job_id") == job_id:
            snap["is_running"] = False
            snap["current_fragment_id"] = None
            snap["finished_at"] = _utc_now_iso()
            snap["stop_requested"] = False
            await self._redis.set(self._frag_snapshot_key, json.dumps(snap))
        await self._redis.delete(self._frag_lock_key)

    async def is_fragment_stop_requested(
            self,
            job_id: str,
    ) -> bool:
        snap = await self._get_json(self._frag_snapshot_key)
        if not snap or snap.get("job_id") != job_id:
            return False
        return bool(snap.get("stop_requested"))

    async def update_fragment_job_cursor(
            self,
            job_id: str,
            last_fragment_id: Optional[int],
    ) -> None:
        key = self._frag_manifest_key(job_id)
        raw = await self._redis.get(key)
        if not raw:
            return
        manifest = json.loads(raw)
        manifest["last_fragment_id"] = last_fragment_id
        await self._redis.set(key, json.dumps(manifest))

    async def _get_json(
            self,
            key: str,
    ) -> Optional[dict[str, Any]]:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("Redis value for key was not valid JSON.", extra={"redis_key": key})
            return None
        return data if isinstance(data, dict) else None
