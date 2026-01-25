from abc import ABC, abstractmethod

from app.domain.dtos.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary_response import DocumentSummaryResponse


class DocumentSummaryServiceInterface(ABC):
    @abstractmethod
    async def execute_document_summary(self,
                                       request_body: DocumentSummaryRequest) -> DocumentSummaryResponse:
        pass
