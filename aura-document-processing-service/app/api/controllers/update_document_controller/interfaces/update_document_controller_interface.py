from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface
)
from app.domain.dtos.update_document.update_document_request import UpdateDocumentRequest
from app.domain.dtos.update_document.update_document_response import UpdateDocumentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class UpdateDocumentControllerInterface(ABC):
    @abstractmethod
    async def update_document(
            self,
            document_id: int,
            update_document_request: UpdateDocumentRequest,
            update_document_service: UpdateDocumentServiceInterface,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> UpdateDocumentResponse:
        pass
