from abc import ABC, abstractmethod
from typing import Any, Optional

from app.domain.constants.document.bulk_operation import BulkOperation


class BulkJobProgressStoreInterface(ABC):
    """Tracks the progress of a single in-flight bulk operation per ``BulkOperation``.

    Backed by Redis so the (background) fan-out, the per-document consumers and the
    HTTP status/stop endpoints all observe the same snapshot.
    """

    @abstractmethod
    async def begin_job(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
            total: int,
    ) -> None:
        ...

    @abstractmethod
    async def mark(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
            processed_increment: int = 0,
            failed_increment: int = 0,
    ) -> None:
        ...

    @abstractmethod
    async def append_error(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
            error: dict[str, Any],
    ) -> None:
        ...

    @abstractmethod
    async def request_stop(
            self,
            *,
            operation: BulkOperation,
    ) -> bool:
        ...

    @abstractmethod
    async def is_stopped(
            self,
            *,
            operation: BulkOperation,
            job_id: str,
    ) -> bool:
        ...

    @abstractmethod
    async def get_snapshot(
            self,
            *,
            operation: BulkOperation,
    ) -> Optional[dict[str, Any]]:
        ...
