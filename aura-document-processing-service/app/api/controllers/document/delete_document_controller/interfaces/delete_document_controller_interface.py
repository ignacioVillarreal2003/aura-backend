from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio.session import AsyncSession
from fastapi import Response

from app.application.services.delete_document_service.interfaces.delete_document_service_interface import (
    DeleteDocumentServiceInterface
)
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DeleteDocumentControllerInterface(ABC):
    @abstractmethod
    async def soft_delete_documents_by_chat(
            self,
            chat_id: int,
            delete_document_service: DeleteDocumentServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> Response:
        pass

    @abstractmethod
    async def soft_delete_document(
            self,
            document_id: int,
            delete_document_service: DeleteDocumentServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> Response:
        pass

    @abstractmethod
    async def hard_delete_documents_by_chat(
            self,
            chat_id: int,
            delete_document_service: DeleteDocumentServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> Response:
        pass

    @abstractmethod
    async def hard_delete_document(
            self,
            document_id: int,
            delete_document_service: DeleteDocumentServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> Response:
        pass
