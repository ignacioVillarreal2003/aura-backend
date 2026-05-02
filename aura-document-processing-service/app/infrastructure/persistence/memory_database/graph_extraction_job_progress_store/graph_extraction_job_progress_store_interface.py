from abc import ABC, abstractmethod
from typing import Any, Optional


class GraphExtractionJobProgressStoreInterface(ABC):
    """Tracks per-document graph-extraction job progress in Redis.

    Unlike the fragment-post-process store (which only tracks ONE global
    job at a time), this store keys snapshots by ``document_id`` because
    extraction is event-driven and many documents can run concurrently.
    """

    @abstractmethod
    async def try_acquire_extraction_lock(
            self,
            *,
            document_id: int,
            job_id: str,
    ) -> bool:
        pass

    @abstractmethod
    async def release_extraction_lock(
            self,
            *,
            document_id: int,
    ) -> None:
        pass

    @abstractmethod
    async def begin_job(
            self,
            *,
            job_id: str,
            document_id: int,
            total_fragments: int,
    ) -> None:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def append_error(
            self,
            *,
            job_id: str,
            document_id: int,
            error: dict[str, Any],
    ) -> None:
        pass

    @abstractmethod
    async def complete_job(
            self,
            *,
            job_id: str,
            document_id: int,
    ) -> None:
        pass

    @abstractmethod
    async def get_snapshot(
            self,
            *,
            document_id: int,
    ) -> Optional[dict[str, Any]]:
        pass
