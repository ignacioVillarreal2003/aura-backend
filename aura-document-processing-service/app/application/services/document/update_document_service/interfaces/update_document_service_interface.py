from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.dtos.document.update_document.update_document_request import UpdateDocumentRequest


class UpdateDocumentServiceInterface(ABC):
    @abstractmethod
    async def update_document_manage(
            self,
            document_id: int,
            update_document_request: UpdateDocumentRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentResponse:
        pass
