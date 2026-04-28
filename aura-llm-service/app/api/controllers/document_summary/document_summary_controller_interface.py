from abc import ABC, abstractmethod

from app.application.services.document.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary.document_summary_response import DocumentSummaryResponse


class DocumentSummaryControllerInterface(ABC):
    @abstractmethod
    async def execute_document_summary(
            self,
            document_summary_request: DocumentSummaryRequest,
            document_summary_service: DocumentSummaryServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> DocumentSummaryResponse:
        pass
