import logging
import tempfile
import time
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import UploadFile, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.create_document_service.create_document_service_request_validator import (
    CreateDocumentServiceRequestValidator
)
from app.application.services.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings
)
from app.application.services.create_document_service.exceptions.create_document_service_exception import (
    DocumentValidationException,
    DocumentUploadException,
    DocumentPersistenceException,
    CreateDocumentServiceException
)
from app.application.services.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface
)
from app.application.services.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface
)
from app.domain.constants.document_mime_type import DocumentMimeType
from app.domain.constants.document_status import DocumentStatus
from app.domain.constants.document_type import DocumentType
from app.domain.dtos.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.create_document.create_document_response import CreateDocumentResponse
from app.domain.models.document import Document
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.repositories.document_repository.document_repository import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import DatabaseException
from app.infrastructure.persistence.storages.document_storage.exceptions.document_storage_exception import (
    DocumentStorageError
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)

logger = logging.getLogger(__name__)


class CreateDocumentService(CreateDocumentServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            document_storage: DocumentStorageInterface,
            document_ingestion_service: DocumentIngestionServiceInterface,
            create_document_service_settings: CreateDocumentServiceSettings
    ):
        self._document_repository = document_repository
        self._document_storage = document_storage
        self._document_ingestion_service = document_ingestion_service
        self._create_document_service_settings = create_document_service_settings

        self._create_document_service_request_validator = CreateDocumentServiceRequestValidator(
            create_document_service_settings=self._create_document_service_settings
        )

        self._documents_created = 0
        self._documents_failed = 0
        self._validation_errors = 0
        self._upload_errors = 0
        self._database_errors = 0
        self._total_bytes_uploaded = 0
        self._last_health_check: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
            cls,
            document_repository: DocumentRepositoryInterface,
            document_storage: DocumentStorageInterface,
            document_ingestion_service: DocumentIngestionServiceInterface,
            **config_kwargs
    ) -> "CreateDocumentService":
        create_document_service_settings = CreateDocumentServiceSettings(
            **config_kwargs
        )

        return cls(
            document_repository=document_repository,
            document_storage=document_storage,
            document_ingestion_service=document_ingestion_service,
            create_document_service_settings=create_document_service_settings
        )

    async def create_document(
            self,
            create_document_request: CreateDocumentRequest,
            raw_document: UploadFile,
            background_tasks: BackgroundTasks,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> CreateDocumentResponse:
        start_time = time.time()
        temp_path: Optional[Path] = None

        logger.info(
            "Starting document creation",
            extra={
                "document_filename": raw_document.filename,
                "content_type": raw_document.content_type,
                "user_id": user.id
            }
        )

        try:
            try:
                self._create_document_service_request_validator.validate_request(
                    create_document_request=create_document_request,
                    raw_document=raw_document
                )

                document_mime_type: DocumentMimeType = self._create_document_service_request_validator.get_document_mime_type(
                    raw_document=raw_document
                )

                logger.info(
                    "Validation completed",
                    extra={
                        "document_type": document_mime_type.value
                    }
                )

            except Exception as e:
                self._validation_errors += 1
                logger.error(
                    "Validation failed",
                    extra={
                        "error": str(e),
                        "document_filename": raw_document.filename
                    }
                )
                raise DocumentValidationException(f"Document validation failed: {str(e)}") from e

            temp_path = await self._save_temp_file(raw_document)

            if raw_document.size:
                self._total_bytes_uploaded += raw_document.size

            try:
                object_name = await self._document_storage.upload_document(
                    file=raw_document,
                    additional_metadata={
                        "user_id": user.id,
                        "document_mime_type": document_mime_type.value,
                    }
                )

                logger.info(
                    "File uploaded to storage",
                    extra={
                        "object_name": object_name
                    }
                )

            except DocumentStorageError as e:
                self._upload_errors += 1
                logger.error(
                    "Storage upload failed",
                    extra={
                        "error": str(e),
                        "document_filename": raw_document.filename
                    }
                )
                raise DocumentUploadException(f"Failed to upload document to storage: {str(e)}") from e

            document = Document(
                name=raw_document.filename,
                original_name=raw_document.filename,
                mime_type=document_mime_type,
                status=DocumentStatus.uploaded,
                storage_url=object_name,
                file_size_bytes=raw_document.size,
                is_active=True,
                processing_started_at=datetime.utcnow(),
                created_by=user.id,
                created_at=datetime.utcnow()
            )

            try:
                database_document = await self._document_repository.create_document(
                    document=document,
                    database_session=database_session
                )

                logger.info(
                    "Document persisted to database",
                    extra={
                        "document_id": database_document.id
                    }
                )

            except DatabaseException as e:
                self._database_errors += 1
                logger.error(
                    "Database persistence failed",
                    extra={
                        "error": str(e),
                        "document_filename": raw_document.filename
                    }
                )

                try:
                    await self._document_storage.delete_document(object_name)
                    logger.info("Compensating action: deleted from storage")
                except Exception as cleanup_error:
                    logger.error(
                        f"Failed to cleanup storage after database error: {cleanup_error}"
                    )

                raise DocumentPersistenceException(f"Failed to persist document to database: {str(e)}") from e

            if (self._create_document_service_settings.enable_background_processing
                    and temp_path):
                background_tasks.add_task(
                    self._process_document_background,
                    document=database_document,
                    local_file_path=temp_path
                )

                logger.info(
                    "Document processing scheduled",
                    extra={
                        "document_id": database_document.id
                    }
                )

            self._documents_created += 1

            elapsed = (time.time() - start_time) * 1000

            logger.info(
                "Document creation completed successfully",
                extra={
                    "document_id": database_document.id,
                    "elapsed_ms": round(elapsed, 2),
                    "status": database_document.status
                }
            )

            return CreateDocumentResponse(
                status=database_document.status
            )

        except (
                DocumentValidationException,
                DocumentUploadException,
                DocumentPersistenceException
        ):
            self._documents_failed += 1
            raise

        except Exception as e:
            self._documents_failed += 1
            logger.exception(
                "Unexpected error during document creation",
                extra={
                    "document_filename": raw_document.filename
                }
            )
            raise CreateDocumentServiceException(f"Document creation failed: {str(e)}") from e

    async def _save_temp_file(
            self,
            file: UploadFile
    ) -> Path:
        try:
            temp_dir = Path(tempfile.gettempdir()) / self._create_document_service_settings.temp_dir_prefix
            temp_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            temp_path = temp_dir / f"{int(time.time() * 1000)}_{file.filename}"

            content = await file.read()

            await asyncio.to_thread(temp_path.write_bytes, content)

            await file.seek(0)

            logger.debug(
                "Temporary file saved",
                extra={
                    "path": str(temp_path),
                    "size": len(content)
                }
            )

            return temp_path

        except Exception as e:
            logger.exception("Failed to save temporary file")
            raise IOError(f"Failed to save temporary file: {str(e)}") from e

    async def _process_document_background(
            self,
            document: Document,
            local_file_path: Path
    ) -> None:
        try:
            logger.info(
                "Starting background processing",
                extra={
                    "document_id": document.id
                }
            )

            await self._document_ingestion_service.process_document(
                document=document,
                local_file_path=local_file_path
            )

            logger.info(
                "Background processing completed",
                extra={
                    "document_id": document.id
                }
            )

        except Exception as e:
            logger.exception(
                "Background processing failed",
                extra={
                    "document_id": document.id,
                    "error": str(e)
                }
            )

        finally:
            if (self._create_document_service_settings.cleanup_temp_files and
                    local_file_path.exists()):
                try:
                    await asyncio.to_thread(local_file_path.unlink)
                    logger.debug(
                        "Temporary file cleaned up",
                        extra={
                            "path": str(local_file_path)
                        }
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to cleanup temporary file: {e}",
                        extra={
                            "path": str(local_file_path)
                        }
                    )

    def get_metrics(
            self
    ) -> Dict[str, int]:
        return {
            "documents_created": self._documents_created,
            "documents_failed": self._documents_failed,
            "validation_errors": self._validation_errors,
            "upload_errors": self._upload_errors,
            "database_errors": self._database_errors,
            "total_bytes_uploaded": self._total_bytes_uploaded,
        }
