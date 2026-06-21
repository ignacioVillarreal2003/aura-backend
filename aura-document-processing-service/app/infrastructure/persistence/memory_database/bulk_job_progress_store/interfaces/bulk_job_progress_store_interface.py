from abc import ABC, abstractmethod
from typing import Any, Optional

from app.domain.constants.document.bulk_operation import BulkOperation


class BulkJobProgressStoreInterface(ABC):
    @abstractmethod
    async def begin_job(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
            total: int,
    ) -> None:
        pass

    @abstractmethod
    async def mark(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
            processed_increment: int = 0,
            failed_increment: int = 0,
    ) -> None:
        pass

    @abstractmethod
    async def append_error(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
            error: dict[str, Any],
    ) -> None:
        pass

    @abstractmethod
    async def request_stop(
            self,
            *,
            operation: BulkOperation,
    ) -> bool:
        pass

    @abstractmethod
    async def is_stopped(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
    ) -> bool:
        pass

    @abstractmethod
    async def get_snapshot(
            self,
            *,
            operation: BulkOperation,
    ) -> Optional[dict[str, Any]]:
        pass
