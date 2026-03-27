from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.constants.document_type import DocumentType
from app.domain.dtos.document_query_controller.document_response import (
    DocumentResponse,
    DocumentListResponse
)
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentQueryControllerInterface(ABC):
    @abstractmethod
    async def get_document(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
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
            authenticated_user: AuthenticationResponse
    ) -> DocumentListResponse:
        pass
