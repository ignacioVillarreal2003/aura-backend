from abc import ABC, abstractmethod
from typing import Dict
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dtos.document_creation.document_creation_request import DocumentCreationRequest
from app.domain.dtos.document_creation.document_creation_response import DocumentCreationResponse
from app.domain.dtos.document_creation.document_creation_status_response import DocumentCreationStatusResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentCreationServiceInterface(ABC):
    @abstractmethod
    async def create_document(
            self,
            document_creation_request: DocumentCreationRequest,
            raw_document: UploadFile,
            background_tasks: BackgroundTasks,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> DocumentCreationResponse:
        pass

    @abstractmethod
    async def get_document_creation_status(
            self,
            document_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> DocumentCreationStatusResponse:
        pass

    @abstractmethod
    def get_metrics(
            self
    ) -> Dict[str, int]:
        pass
