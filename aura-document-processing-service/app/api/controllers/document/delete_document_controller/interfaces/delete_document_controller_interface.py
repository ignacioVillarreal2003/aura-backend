from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio.session import AsyncSession
from fastapi import Response

from app.application.services.document.delete_document_service.interfaces.delete_document_service_interface import (
    DeleteDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser


class DeleteDocumentControllerInterface(ABC):
    @abstractmethod
    async def soft_delete_documents_by_chat(
            self,
            chat_id: int,
            delete_document_service: DeleteDocumentServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> Response:
        pass

    @abstractmethod
    async def soft_delete_document(
            self,
            document_id: int,
            delete_document_service: DeleteDocumentServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> Response:
        pass

    @abstractmethod
    async def soft_delete_document_manage(
            self,
            document_id: int,
            delete_document_service: DeleteDocumentServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> Response:
        pass
