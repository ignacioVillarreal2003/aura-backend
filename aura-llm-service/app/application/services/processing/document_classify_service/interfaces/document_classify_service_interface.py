from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.processing.document_classify.classify_document_response import ClassifyDocumentResponse


class DocumentClassifyServiceInterface(ABC):
    @abstractmethod
    async def classify_document(
            self,
            classify_document_request: ClassifyDocumentRequest,
            authenticated_user: AuthenticatedUser,
    ) -> ClassifyDocumentResponse:
        pass
