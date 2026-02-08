from abc import ABC, abstractmethod
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.orm.session import Session

from app.domain.dtos.document_creation.document_creation_request import DocumentCreationRequest
from app.domain.dtos.document_creation.document_creation_response import DocumentCreationResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse


class DocumentCreationServiceInterface(ABC):
    @abstractmethod
    async def create_document(
            self,
            document_creation_request: DocumentCreationRequest,
            raw_document: UploadFile,
            background_tasks: BackgroundTasks,
            db: Session,
            user: AuthenticationResponse
    ) -> DocumentCreationResponse:
        pass
