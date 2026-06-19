from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.bulk_operation import BulkOperation
from app.domain.dtos.document.bulk.bulk_responses import BulkJobStatusResponse, BulkStartResponse
from app.domain.dtos.document.bulk.document_selector import DocumentSelector


class BulkDispatchServiceInterface(ABC):
    @abstractmethod
    async def start(
            self,
            *,
            operation: BulkOperation,
            selector: DocumentSelector,
            user: AuthenticatedUser,
            force: bool = False,
            prefer_docling: bool = False,
            post_process: bool = True,
            post_process_graph: bool = True,
    ) -> BulkStartResponse:
        ...

    @abstractmethod
    async def status(
            self,
            *,
            operation: BulkOperation,
    ) -> BulkJobStatusResponse:
        ...

    @abstractmethod
    async def stop(
            self,
            *,
            operation: BulkOperation,
    ) -> BulkJobStatusResponse:
        ...
