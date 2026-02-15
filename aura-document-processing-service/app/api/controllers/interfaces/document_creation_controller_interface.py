from abc import ABC, abstractmethod
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.application.services.document_creation_service.interfaces.document_creation_service_interface import (
    DocumentCreationServiceInterface
)
from app.domain.dtos.document_creation.document_creation_request import DocumentCreationRequest
from app.domain.dtos.document_creation.document_creation_response import DocumentCreationResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentCreationControllerInterface(ABC):
    @abstractmethod
    async def create_document(
            self,
            background_tasks: BackgroundTasks,
            document_creation_request: DocumentCreationRequest,
            raw_document: UploadFile,
            document_creation_service: DocumentCreationServiceInterface,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> DocumentCreationResponse:
        pass
