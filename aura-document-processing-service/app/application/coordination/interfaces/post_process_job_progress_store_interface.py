from abc import ABC, abstractmethod
from typing import Any, Optional

from app.domain.authentication.authenticated_user import AuthenticatedUser


class PostProcessJobProgressStoreInterface(ABC):
    @abstractmethod
    async def try_begin_document_job(
            self,
            *,
            job_id: str,
            total_documents: int,
            document_ids: list[int],
            triggered_by: AuthenticatedUser,
    ) -> bool:
        pass

    @abstractmethod
    async def abort_document_job(
            self,
            job_id: str,
    ) -> None:
        pass

    @abstractmethod
    async def get_document_job_snapshot(
            self,
    ) -> Optional[dict[str, Any]]:
        pass

    @abstractmethod
    async def request_document_stop(
            self,
    ) -> None:
        pass

    @abstractmethod
    async def get_document_job_manifest(
            self,
            job_id: str,
    ) -> Optional[dict[str, Any]]:
        pass

    @abstractmethod
    async def mark_document_job_progress(
            self,
            job_id: str,
            *,
            current_document_id: Optional[int] = None,
            processed_increment: int = 0,
            failed_increment: int = 0,
    ) -> None:
        pass

    @abstractmethod
    async def append_document_job_error(
            self,
            job_id: str,
            error: dict[str, Any],
    ) -> None:
        pass

    @abstractmethod
    async def complete_document_job(
            self,
            job_id: str,
    ) -> None:
        pass

    @abstractmethod
    async def is_document_stop_requested(
            self,
            job_id: str,
    ) -> bool:
        pass

    @abstractmethod
    async def try_begin_fragment_job(
            self,
            *,
            job_id: str,
            total_fragments: int,
            document_ids: Optional[list[int]],
            triggered_by: AuthenticatedUser,
    ) -> bool:
        pass

    @abstractmethod
    async def abort_fragment_job(
            self,
            job_id: str,
    ) -> None:
        pass

    @abstractmethod
    async def get_fragment_job_snapshot(
            self,
    ) -> Optional[dict[str, Any]]:
        pass

    @abstractmethod
    async def request_fragment_stop(
            self,
    ) -> None:
        pass

    @abstractmethod
    async def get_fragment_job_manifest(
            self,
            job_id: str,
    ) -> Optional[dict[str, Any]]:
        pass

    @abstractmethod
    async def mark_fragment_job_progress(
            self,
            job_id: str,
            *,
            current_fragment_id: Optional[int] = None,
            processed_increment: int = 0,
            failed_increment: int = 0,
    ) -> None:
        pass

    @abstractmethod
    async def append_fragment_job_error(
            self,
            job_id: str,
            error: dict[str, Any],
    ) -> None:
        pass

    @abstractmethod
    async def complete_fragment_job(
            self,
            job_id: str,
    ) -> None:
        pass

    @abstractmethod
    async def is_fragment_stop_requested(
            self,
            job_id: str,
    ) -> bool:
        pass

    @abstractmethod
    async def update_fragment_job_cursor(
            self,
            job_id: str,
            last_fragment_id: Optional[int],
    ) -> None:
        pass
