from abc import ABC, abstractmethod

from app.application.services.document_classify_service.interfaces.document_classify_service_interface import (
    DocumentClassifyServiceInterface,
)
from app.domain.dtos.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.document_classify.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentClassifyControllerInterface(ABC):
    @abstractmethod
    async def classify_document(
            self,
            body: ClassifyDocumentRequest,
            document_classify_service: DocumentClassifyServiceInterface,
            authenticated_user: AuthenticationResponse,
    ) -> ClassifyDocumentResponse:
        pass
