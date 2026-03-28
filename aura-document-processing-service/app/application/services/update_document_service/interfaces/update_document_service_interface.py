from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.update_document_controller.post_process_document_request import PostProcessDocumentRequest
from app.domain.dtos.update_document_controller.post_process_document_response import PostProcessDocumentResponse
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import AuthenticationResponse


class UpdateDocumentServiceInterface(ABC):
    @abstractmethod
    async def post_process_document(
            self,
            document_id: int,
            post_process_document_request: PostProcessDocumentRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> PostProcessDocumentResponse:
        pass
