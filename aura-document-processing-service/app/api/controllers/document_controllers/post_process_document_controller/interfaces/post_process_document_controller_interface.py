from abc import ABC, abstractmethod
from fastapi import Response

from app.application.services.document.post_process_document_service.interfaces.post_process_document_service_interface import (
    PostProcessDocumentServiceInterface
)
from app.domain.dtos.document.post_process_document.post_process_documents_start_response import (
    PostProcessDocumentsStartResponse
)
from app.domain.dtos.document.post_process_document.post_process_documents_request import (
    PostProcessDocumentsRequest
)
from app.domain.dtos.document.post_process_document.post_process_documents_status_response import PostProcessDocumentsStatusResponse
from app.domain.authentication.authenticated_user import AuthenticatedUser


class PostProcessDocumentControllerInterface(ABC):
    @abstractmethod
    async def start_all(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessDocumentsStartResponse:
        pass

    @abstractmethod
    async def start_for_documents(
            self,
            post_process_documents_request: PostProcessDocumentsRequest,
            post_process_document_service: PostProcessDocumentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessDocumentsStartResponse:
        pass

    @abstractmethod
    async def get_status(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessDocumentsStatusResponse:
        pass

    @abstractmethod
    async def stop(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> Response:
        pass
