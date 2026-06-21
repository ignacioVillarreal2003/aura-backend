from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.constants.document.document_type import DocumentType
from app.domain.dtos.document.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.dtos.document.document_query.document_status_response import DocumentStatusResponse
from app.domain.authentication.authenticated_user import AuthenticatedUser


class DocumentQueryServiceInterface(ABC):
    @abstractmethod
    async def get_document_manage(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentResponse:
        pass

    @abstractmethod
    async def get_document_status_manage(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentStatusResponse:
        pass

    @abstractmethod
    async def get_document_status(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentStatusResponse:
        pass

    @abstractmethod
    async def get_documents_manage(
            self,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
            page: Optional[int] = None,
            size: Optional[int] = None,
            name: Optional[str] = None,
            description: Optional[str] = None,
            category: Optional[str] = None,
            document_type: Optional[DocumentType] = None,
            created_from: Optional[datetime] = None,
            created_to: Optional[datetime] = None,
    ) -> DocumentListResponse:
        pass

    @abstractmethod
    async def get_documents_by_chat(
            self,
            chat_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
            page: Optional[int] = None,
            size: Optional[int] = None,
    ) -> DocumentListResponse:
        pass

