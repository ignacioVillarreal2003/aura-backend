from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface
)
from app.domain.dtos.update_document_controller.post_process_document_request import PostProcessDocumentRequest
from app.domain.dtos.update_document_controller.post_process_document_response import PostProcessDocumentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class UpdateDocumentControllerInterface(ABC):
    @abstractmethod
    async def post_process_document(
            self,
            document_id: int,
            post_process_document_request: PostProcessDocumentRequest,
            update_document_service: UpdateDocumentServiceInterface,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> PostProcessDocumentResponse:
        pass
