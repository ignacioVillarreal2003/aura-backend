from abc import ABC, abstractmethod
from typing import Optional


class GraphExtractionLockStoreInterface(ABC):
    """Per-document mutex for knowledge graph extraction.

    Extraction is a purge-then-rebuild with running confidence averages, which is
    not safe to run concurrently for the same document; this lock serializes it.
    """

    @abstractmethod
    async def try_acquire_extraction_lock(
            self,
            *,
            document_id: int,
            job_id: str,
    ) -> bool:
        """Acquire the per-document extraction lock. Returns False if already held."""

    @abstractmethod
    async def release_extraction_lock(
            self,
            *,
            document_id: int,
            job_id: Optional[str] = None,
    ) -> None:
        """Release the lock. When ``job_id`` is given, release only if this job owns it."""
