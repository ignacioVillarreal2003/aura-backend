from abc import ABC, abstractmethod
from fastapi import Request

from app.application.services.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface
)
from app.domain.dtos.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary.document_summary_response import DocumentSummaryResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentSummaryControllerInterface(ABC):
    @abstractmethod
    async def execute_document_summary(
            self,
            request: Request,
            document_summary_request: DocumentSummaryRequest,
            document_summary_service: DocumentSummaryServiceInterface,
            user: AuthenticationResponse
    ) -> DocumentSummaryResponse:
        pass
