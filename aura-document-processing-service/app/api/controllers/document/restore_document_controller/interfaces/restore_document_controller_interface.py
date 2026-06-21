from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.document.restore_document_service.interfaces.restore_document_service_interface import (
    RestoreDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_query.document_response import DocumentResponse


class RestoreDocumentControllerInterface(ABC):
    @abstractmethod
    async def restore_document_manage(
            self,
            document_id: int,
            restore_document_service: RestoreDocumentServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentResponse:
        pass
