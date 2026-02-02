from abc import ABC, abstractmethod
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.orm.session import Session

from app.domain.dtos.document_creation_request import DocumentCreationRequest
from app.domain.dtos.document_creation_response import DocumentCreationResponse


class DocumentCreationServiceInterface(ABC):
    @abstractmethod
    async def execute_document_creation(
            self,
            document_creation_request: DocumentCreationRequest,
            raw_document: UploadFile,
            background_tasks: BackgroundTasks,
            db: Session
    ) -> DocumentCreationResponse:
        pass
