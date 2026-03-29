from abc import ABC, abstractmethod
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.document.create_document.create_document_response import CreateDocumentResponse
from app.domain.authentication.authenticated_user import AuthenticatedUser


class CreateDocumentServiceInterface(ABC):
    @abstractmethod
    async def create_document(
            self,
            create_document_request: CreateDocumentRequest,
            raw_document: UploadFile,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> CreateDocumentResponse:
        pass
