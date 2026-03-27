from abc import ABC, abstractmethod
from typing import List

from app.domain.dtos.post_process_document_controller.post_process_start_response import PostProcessStartResponse
from app.domain.dtos.post_process_document_controller.post_process_status_response import PostProcessStatusResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


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
