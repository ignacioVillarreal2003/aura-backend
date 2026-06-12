from abc import ABC, abstractmethod

from app.application.services.processing.document_classify_service.interfaces.document_classify_service_interface import (
    DocumentClassifyServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.processing.document_classify.classify_document_response import ClassifyDocumentResponse


class DocumentClassifyControllerInterface(ABC):
    @abstractmethod
    async def classify_document(
            self,
            classify_document_request: ClassifyDocumentRequest,
            document_classify_service: DocumentClassifyServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> ClassifyDocumentResponse:
        pass
