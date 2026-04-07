from abc import ABC, abstractmethod

from app.domain.dtos.document.post_process_document.post_process_documents_start_response import (
    PostProcessDocumentsStartResponse
)
from app.domain.dtos.document.post_process_document.post_process_documents_request import (
    PostProcessDocumentsRequest,
)
from app.domain.dtos.document.post_process_document.post_process_documents_status_response import PostProcessDocumentsStatusResponse
from app.domain.authentication.authenticated_user import AuthenticatedUser


class PostProcessDocumentServiceInterface(ABC):
    @abstractmethod
    async def start_all(
            self,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessDocumentsStartResponse:
        pass

    @abstractmethod
    async def start_for_documents(
            self,
            post_process_documents_request: PostProcessDocumentsRequest,
            authenticated_user: AuthenticatedUser
    ) -> PostProcessDocumentsStartResponse:
        pass

    @abstractmethod
    def get_status(
            self
    ) -> PostProcessDocumentsStatusResponse:
        pass

    @abstractmethod
    async def stop(
            self
    ) -> None:
        pass
