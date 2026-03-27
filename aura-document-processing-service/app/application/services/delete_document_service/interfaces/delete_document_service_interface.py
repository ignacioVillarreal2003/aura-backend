from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DeleteDocumentServiceInterface(ABC):
    @abstractmethod
    async def soft_delete_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> None:
        pass

    @abstractmethod
    async def soft_delete_documents_by_chat(
            self,
            chat_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> None:
        pass

    @abstractmethod
    async def hard_delete_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> None:
        pass

    @abstractmethod
    async def hard_delete_documents_by_chat(
            self,
            chat_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> None:
        pass
