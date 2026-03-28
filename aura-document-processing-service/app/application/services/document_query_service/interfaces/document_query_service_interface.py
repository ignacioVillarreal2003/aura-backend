from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.constants.document.document_type import DocumentType
from app.domain.dtos.document.document_query_controller.document_response import DocumentListResponse, DocumentResponse
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import AuthenticationResponse


class DocumentQueryServiceInterface(ABC):
    @abstractmethod
    async def get_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> DocumentResponse:
        pass

    @abstractmethod
    async def get_documents(
            self,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse,
            page: Optional[int] = None,
            size: Optional[int] = None,
            name: Optional[str] = None,
            description: Optional[str] = None,
            category: Optional[str] = None,
            type: Optional[DocumentType] = None,
            created_from: Optional[datetime] = None,
            created_to: Optional[datetime] = None,
    ) -> DocumentListResponse:
        pass
