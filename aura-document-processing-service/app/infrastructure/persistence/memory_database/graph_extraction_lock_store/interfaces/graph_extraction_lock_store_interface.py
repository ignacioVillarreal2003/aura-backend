from abc import ABC, abstractmethod
from typing import Optional


class GraphExtractionLockStoreInterface(ABC):

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
            job_id: Optional[str] = None,
    ) -> None:
        pass
