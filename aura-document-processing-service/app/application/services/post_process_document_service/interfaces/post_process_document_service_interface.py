from abc import ABC, abstractmethod
from typing import List

from app.domain.dtos.document.post_process_document_controller.post_process_document_start_response import PostProcessStartResponse
from app.domain.dtos.document.post_process_document_controller.post_process_document_status_response import PostProcessStatusResponse
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import AuthenticationResponse


class PostProcessDocumentServiceInterface(ABC):
    @abstractmethod
    async def start_all(
            self,
            authenticated_user: AuthenticationResponse
    ) -> PostProcessStartResponse:
        pass

    @abstractmethod
    async def start_for_documents(
            self,
            document_ids: List[int],
            authenticated_user: AuthenticationResponse
    ) -> PostProcessStartResponse:
        pass

    @abstractmethod
    def get_status(self) -> PostProcessStatusResponse:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass
