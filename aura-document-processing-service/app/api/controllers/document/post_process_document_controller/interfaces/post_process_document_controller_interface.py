from abc import ABC, abstractmethod

from app.application.services.post_process_document_service.interfaces.post_process_document_service_interface import (
    PostProcessDocumentServiceInterface
)
from app.domain.dtos.post_process_document_controller.post_process_documents_request import (
    PostProcessDocumentsRequest
)
from app.domain.dtos.post_process_document_controller.post_process_start_response import PostProcessStartResponse
from app.domain.dtos.post_process_document_controller.post_process_status_response import PostProcessStatusResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class PostProcessDocumentControllerInterface(ABC):
    @abstractmethod
    async def start_all(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface,
            authenticated_user: AuthenticationResponse
    ) -> PostProcessStartResponse:
        pass

    @abstractmethod
    async def start_for_documents(
            self,
            post_process_documents_request: PostProcessDocumentsRequest,
            post_process_document_service: PostProcessDocumentServiceInterface,
            authenticated_user: AuthenticationResponse
    ) -> PostProcessStartResponse:
        pass

    @abstractmethod
    async def get_status(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface,
            authenticated_user: AuthenticationResponse
    ) -> PostProcessStatusResponse:
        pass

    @abstractmethod
    async def stop(
            self,
            post_process_document_service: PostProcessDocumentServiceInterface,
            authenticated_user: AuthenticationResponse
    ) -> None:
        pass
