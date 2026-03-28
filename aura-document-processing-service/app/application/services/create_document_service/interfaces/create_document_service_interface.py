from abc import ABC, abstractmethod
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.document.create_document.create_document_response import CreateDocumentResponse
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import AuthenticationResponse


class CreateDocumentServiceInterface(ABC):
    @abstractmethod
    async def create_document(
            self,
            create_document_request: CreateDocumentRequest,
            raw_document: UploadFile,
            background_tasks: BackgroundTasks,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse,
    ) -> CreateDocumentResponse:
        pass
