from abc import ABC, abstractmethod
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface
)
from app.domain.dtos.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.create_document.create_document_response import CreateDocumentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class CreateDocumentControllerInterface(ABC):
    @abstractmethod
    async def create_document(
            self,
            background_tasks: BackgroundTasks,
            create_document_request: CreateDocumentRequest,
            raw_document: UploadFile,
            create_document_service: CreateDocumentServiceInterface,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> CreateDocumentResponse:
        pass
