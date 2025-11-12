import logging
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.orm import Session

from app.application.services.ingestion_service import IngestionService
from app.configuration.environment_variables import environment_variables
from app.domain.constants.document_type import DocumentType
from app.application.exceptions.exceptions import UnsupportedFileTypeError, ValidationError, StorageError, DatabaseError
from app.domain.dtos.document_request import DocumentRequest
from app.domain.models.document import Document
from app.domain.dtos.document_response import DocumentResponseSchema
from app.infrastructure.persistence.repositories.document_repository import DocumentRepository
from app.infrastructure.persistence.storages.file_storage_repository import FileStorageRepository


logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(self,
                 document_repository: DocumentRepository,
                 file_storage_repository: FileStorageRepository,
                 ingestion_service: IngestionService):
        self.ingestion_service = ingestion_service
        self.document_repository = document_repository
        self.file_storage_repository = file_storage_repository

    async def create(self,
                              request: DocumentRequest,
                              file: UploadFile,
                              db: Session,
                     background_tasks: BackgroundTasks) -> DocumentResponseSchema:
        document_type = self._validate_type(file)
        self._validate_size(file)

        temp_dir = Path(tempfile.gettempdir()) / "uploads"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / file.filename

        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Archivo temporal guardado en: {temp_path}")

        try:
            logger.info("Uploading file to storage")
            path = self.file_storage_repository.upload(file, temp_path)
            logger.info("File uploaded to storage", extra={"path": path})
        except StorageError:
            raise

        document = Document(
            file_name=file.filename,
            type=document_type,
            path=path,
            created_by=1,
            created_at=datetime.now()
        )

        try:
            logger.info("Persisting document to database")
            db_document = self.document_repository.create(document, db)
            logger.info("Document persisted", extra={"document_id": db_document.id})
        except DatabaseError:
            raise

        background_tasks.add_task(
            self.ingestion_service.process_document,
            db_document,
            db,
            temp_path
        )
        logger.info(f"Proceso de ingesta lanzado en background para documento {db_document.id}")

        return DocumentResponseSchema(
            id=db_document.id,
            file_name=db_document.file_name,
            status=db_document.status
        )

    def _validate_type(self, file) -> DocumentType:
        mapping: Dict[str, DocumentType] = {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocumentType.docx,
            "application/pdf": DocumentType.pdf,
        }
        if file is None:
            logger.warning("No file provided in request")
            raise ValidationError("No file provided")
        if file.content_type not in mapping:
            logger.warning("Unsupported content type", extra={"content_type": file.content_type})
            raise UnsupportedFileTypeError("Only PDF and DOCX files are supported")
        return mapping[file.content_type]

    def _validate_size(self, file):
        max_bytes = environment_variables.max_file_size_mb * 1024 * 1024
        if hasattr(file, "size") and file.size and file.size > max_bytes:
            logger.warning("File exceeds max size", extra={
                "size": getattr(file, "size", None),
                "max_bytes": max_bytes
            })
            raise ValidationError(f"File exceeds max size ({environment_variables.max_file_size_mb} MB)")
