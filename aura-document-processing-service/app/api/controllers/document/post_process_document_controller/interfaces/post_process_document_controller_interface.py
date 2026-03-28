from abc import ABC, abstractmethod
from fastapi import Response

from app.application.services.post_process_document_service.interfaces.post_process_document_service_interface import (
    PostProcessDocumentServiceInterface
)
from app.domain.dtos.document.post_process_document_controller.post_process_document_start_response import (
    PostProcessDocumentStartResponse
)
from app.domain.dtos.document.post_process_document_controller.post_process_documents_request import (
    PostProcessDocumentsRequest
)
from app.domain.dtos.document.post_process_document_controller.post_process_document_status_response import PostProcessStatusResponse
from app.domain.models.authenticated_user import AuthenticatedUser


class PostProcessDocumentControllerInterface(ABC):
    @abstractmethod
    async def start_all(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessDocumentStartResponse:
        pass

    @abstractmethod
    async def start_for_documents(
            self,
            post_process_documents_request: PostProcessDocumentsRequest,
            post_process_document_service: PostProcessDocumentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessDocumentStartResponse:
        pass

    @abstractmethod
    async def get_status(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessStatusResponse:
        pass

    @abstractmethod
    async def stop(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface,
            authenticated_user: AuthenticatedUser
    ) -> Response:
        pass
