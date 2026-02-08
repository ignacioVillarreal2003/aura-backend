import logging
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.orm import Session

from app.application.services.document_creation_service.document_creation_service_configuration import (
    DocumentCreationServiceConfiguration
)
from app.application.services.document_creation_service.document_creation_service_request_validator import (
    DocumentCreationServiceRequestValidator
)
from app.application.services.document_creation_service.interfaces.document_creation_service_interface import (
    DocumentCreationServiceInterface
)
from app.application.services.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface
)
from app.domain.constants.document_type import DocumentType
from app.domain.dtos.document_creation.document_creation_request import DocumentCreationRequest
from app.domain.models.document import Document
from app.domain.dtos.document_creation.document_creation_response import DocumentCreationResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.repositories.document_repository.document_repository import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.repositories.exceptions.database_exceptions import DatabaseError
from app.infrastructure.persistence.storages.document_storage.exceptions.document_storage_exception import (
    DocumentStorageError
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)

logger = logging.getLogger(__name__)


class DocumentCreationService(DocumentCreationServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            document_storage: DocumentStorageInterface,
            document_ingestion_service: DocumentIngestionServiceInterface,
            document_creation_service_configuration: DocumentCreationServiceConfiguration
    ):
        self._document_ingestion_service = document_ingestion_service
        self._document_repository = document_repository
        self._document_storage = document_storage

        self._document_creation_service_configuration = document_creation_service_configuration or DocumentCreationServiceConfiguration()

        self._document_creation_service_request_validator = DocumentCreationServiceRequestValidator(
            document_creation_service_configuration=self._document_creation_service_configuration
        )

        logger.info("DocumentCreationService initialized")

    @classmethod
    def create(
            cls,
            document_repository: DocumentRepositoryInterface,
            document_storage: DocumentStorageInterface,
            document_ingestion_service: DocumentIngestionServiceInterface,
            max_file_size_mb: Optional[int] = None
    ) -> "DocumentCreationService":
        config_kwargs = {}

        if max_file_size_mb is not None:
            config_kwargs['max_file_size_mb'] = max_file_size_mb

        document_creation_service_configuration = DocumentCreationServiceConfiguration(
            **config_kwargs
        )

        return cls(
            document_repository=document_repository,
            document_storage=document_storage,
            document_ingestion_service=document_ingestion_service,
            document_creation_service_configuration=document_creation_service_configuration
        )

    async def create_document(
            self,
            document_creation_request: DocumentCreationRequest,
            raw_document: UploadFile,
            background_tasks: BackgroundTasks,
            db: Session,
            user: AuthenticationResponse
    ) -> DocumentCreationResponse:
        logger.info("Starting document creation execution")

        self._document_creation_service_request_validator.validate_request(
            document_creation_request=document_creation_request,
            raw_document=raw_document
        )

        document_type: DocumentType = self._document_creation_service_request_validator.get_raw_document_type(
            raw_document=raw_document
        )

        temp_dir = Path(tempfile.gettempdir()) / "uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / raw_document.filename

        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(raw_document.file, buffer)

        logger.info("Temporary file saved")

        try:
            logger.info("Uploading file to storage")
            path = self._document_storage.upload_document(
                document=raw_document
            )
            logger.info("File uploaded to storage")
        except DocumentStorageError:
            raise

        document = Document(
            name=raw_document.filename,
            type=document_type,
            path=path,
            created_by=user.id,
            created_at=datetime.now()
        )

        try:
            logger.info("Persisting document to database")
            db_document = self._document_repository.create_document(
                document=document,
                db=db
            )
            logger.info("Document persisted")
        except DatabaseError:
            raise

        background_tasks.add_task(
            self._document_ingestion_service.process_document,
            document=db_document,
            local_file_path=temp_path
        )

        logger.info("Document creation executed successfully")

        return DocumentCreationResponse(
            status=db_document.status
        )
