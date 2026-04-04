from abc import ABC, abstractmethod
from typing import Optional

from app.domain.dtos.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary.document_summary_response import DocumentSummaryResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentSummaryServiceInterface(ABC):
    @abstractmethod
    async def execute_document_summary(
            self,
            document_summary_request: DocumentSummaryRequest,
            user: AuthenticationResponse,
            authorization: Optional[str] = None
    ) -> DocumentSummaryResponse:
        pass
