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
            prefer_docling: bool = False,
            enrich: bool = True,
            graph_extract: bool = True,
    ) -> BulkStartResponse:
        pass

    @abstractmethod
    async def status(
            self,
            *,
            operation: BulkOperation,
    ) -> BulkJobStatusResponse:
        pass

    @abstractmethod
    async def stop(
            self,
            *,
            operation: BulkOperation,
    ) -> BulkJobStatusResponse:
        pass
