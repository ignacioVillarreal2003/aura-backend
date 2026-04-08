from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.document.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.constants.document.document_type import DocumentType
from app.domain.dtos.document.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.authentication.authenticated_user import AuthenticatedUser


class DocumentQueryControllerInterface(ABC):
    @abstractmethod
    async def get_document(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> DocumentResponse:
        pass

    @abstractmethod
    async def get_documents(
            self,
            page: Optional[int],
            size: Optional[int],
            name: Optional[str],
            description: Optional[str],
            category: Optional[str],
            type: Optional[DocumentType],
            created_from: Optional[datetime],
            created_to: Optional[datetime],
            document_query_service: DocumentQueryServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> DocumentListResponse:
        pass
