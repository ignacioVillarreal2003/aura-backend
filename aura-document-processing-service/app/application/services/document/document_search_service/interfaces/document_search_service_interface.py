from abc import ABC, abstractmethod
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_search.document_search_request import DocumentSearchRequest
from app.domain.dtos.document.document_search.document_search_response import DocumentSearchListResponse


class DocumentSearchServiceInterface(ABC):
    @abstractmethod
    async def search_documents_by_content(
            self,
            document_search_request: DocumentSearchRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
            authorization_header: Optional[str] = None,
    ) -> DocumentSearchListResponse:
        pass
