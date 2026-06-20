from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.document.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface,
)
from app.domain.constants.document.document_type import DocumentType
from app.domain.dtos.document.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.dtos.document.document_query.document_status_response import DocumentStatusResponse
from app.domain.authentication.authenticated_user import AuthenticatedUser


class DocumentQueryControllerInterface(ABC):
    @abstractmethod
    async def get_document_manage(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentResponse:
        pass

    @abstractmethod
    async def get_document_status_manage(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentStatusResponse:
        pass

    @abstractmethod
    async def get_document_status(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentStatusResponse:
        pass

    @abstractmethod
    async def get_documents_manage(
            self,
            page: int,
            size: int,
            name: Optional[str],
            description: Optional[str],
            category: Optional[str],
            document_type: Optional[DocumentType],
            created_from: Optional[datetime],
            created_to: Optional[datetime],
            document_query_service: DocumentQueryServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentListResponse:
        pass

    @abstractmethod
    async def get_documents_by_chat(
            self,
            chat_id: int,
            page: Optional[int],
            size: Optional[int],
            document_query_service: DocumentQueryServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentListResponse:
        pass
