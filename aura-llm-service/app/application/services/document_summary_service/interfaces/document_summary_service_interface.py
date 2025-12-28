from abc import ABC, abstractmethod

from app.application.services.document_summary_service.document_summary_configuration import \
    DocumentSummaryConfiguration
from app.domain.dtos.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary_response import DocumentSummaryResponse


class DocumentSummaryServiceInterface(ABC):
    @abstractmethod
    async def execute_document_summary(self,
                                       document_summary_request: DocumentSummaryRequest) -> DocumentSummaryResponse:
        pass

    @property
    @abstractmethod
    def configuration(self) -> DocumentSummaryConfiguration:
        pass

    @property
    @abstractmethod
    def is_llm_initialized(self) -> bool:
        pass
