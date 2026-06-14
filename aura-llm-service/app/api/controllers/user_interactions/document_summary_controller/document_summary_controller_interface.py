from abc import ABC, abstractmethod
from starlette.responses import StreamingResponse

from app.application.services.user_interactions.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.user_interactions.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.user_interactions.document_summary.document_summary_response import DocumentSummaryResponse


class DocumentSummaryControllerInterface(ABC):
    @abstractmethod
    async def execute_document_summary(
            self,
            document_summary_request: DocumentSummaryRequest,
            document_summary_service: DocumentSummaryServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentSummaryResponse:
        pass

    @abstractmethod
    async def execute_document_summary_stream(
            self,
            document_summary_request: DocumentSummaryRequest,
            document_summary_service: DocumentSummaryServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> StreamingResponse:
        pass
