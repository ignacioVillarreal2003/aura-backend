from abc import ABC, abstractmethod
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.orm.session import Session

from app.application.services.interfaces.document_creation_service_interface import DocumentCreationServiceInterface
from app.domain.dtos.document_creation_request import DocumentCreationRequest
from app.domain.dtos.document_creation_response import DocumentCreationResponse


class DocumentCreationControllerInterface(ABC):
    @abstractmethod
    async def execute_document_creation(
            self,
            background_tasks: BackgroundTasks,
            document_creation_request: DocumentCreationRequest,
            document: UploadFile,
            document_creation_service: DocumentCreationServiceInterface,
            db: Session
    ) -> DocumentCreationResponse:
        pass
