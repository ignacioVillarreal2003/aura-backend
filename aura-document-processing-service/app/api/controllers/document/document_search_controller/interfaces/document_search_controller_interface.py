from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.document.document_search_service.interfaces.document_search_service_interface import (
    DocumentSearchServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_search.document_search_request import DocumentSearchRequest
from app.domain.dtos.document.document_search.document_search_response import DocumentSearchListResponse


class DocumentSearchControllerInterface(ABC):
    @abstractmethod
    async def search_documents_by_content(
            self,
            document_search_request: DocumentSearchRequest,
            document_search_service: DocumentSearchServiceInterface,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentSearchListResponse:
        pass
