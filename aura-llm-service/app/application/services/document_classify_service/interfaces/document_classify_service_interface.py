from abc import ABC, abstractmethod

from app.domain.dtos.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.document_classify.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentClassifyServiceInterface(ABC):
    @abstractmethod
    async def classify_document(
            self,
            request: ClassifyDocumentRequest,
            authenticated_user: AuthenticationResponse,
    ) -> ClassifyDocumentResponse:
        pass
