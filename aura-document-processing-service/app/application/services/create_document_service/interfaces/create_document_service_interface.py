from abc import ABC, abstractmethod
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.create_document.create_document_response import CreateDocumentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class CreateDocumentServiceInterface(ABC):
    @abstractmethod
    async def create_document(
            self,
            create_document_request: CreateDocumentRequest,
            raw_document: UploadFile,
            background_tasks: BackgroundTasks,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> CreateDocumentResponse:
        pass
