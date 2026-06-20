from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.document.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.dtos.document.update_document.update_document_request import UpdateDocumentRequest


class UpdateDocumentControllerInterface(ABC):
    @abstractmethod
    async def update_document_manage(
            self,
            document_id: int,
            update_document_request: UpdateDocumentRequest,
            update_document_service: UpdateDocumentServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentResponse:
        pass
