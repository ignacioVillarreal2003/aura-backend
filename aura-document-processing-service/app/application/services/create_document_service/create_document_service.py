import asyncio
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentServiceException,
    CreateDocumentPersistenceException,
    CreateDocumentUploadException,
    CreateDocumentValidationException
)
from app.application.services.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface
)
from app.application.services.create_document_service.create_document_service_request_validator import (
    CreateDocumentServiceRequestValidator
)
from app.application.services.create_document_service.create_document_service_settings import CreateDocumentServiceSettings
from app.application.services.create_document_service.create_document_service_utils import CreateDocumentServiceUtils
from app.application.services.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface
)
from app.domain.constants.document_mime_type import DocumentMimeType
from app.domain.constants.document_status import DocumentStatus
from app.domain.dtos.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.create_document.create_document_response import CreateDocumentResponse
from app.domain.models.document import Document
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import DatabaseException
from app.infrastructure.persistence.storages.document_storage.exceptions.document_storage_exception import (
    DocumentStorageException
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
            create_document_service_settings: Optional[CreateDocumentServiceSettings] = None
    ):
        self._document_repository = document_repository
        self._document_storage = document_storage
        self._document_ingestion_service = document_ingestion_service
        self._create_document_service_settings = create_document_service_settings or CreateDocumentServiceSettings()

        self._create_document_service_request_validator = CreateDocumentServiceRequestValidator(
            create_document_service_settings=self._create_document_service_settings
        )
        self._create_document_service_utils = CreateDocumentServiceUtils(
            create_document_service_settings=self._create_document_service_settings
        )

        self._deduplication_lock = asyncio.Lock()
        self._recent_hashes: dict[str, datetime] = {}

    async def create_document(
            self,
            create_document_request: CreateDocumentRequest,
            raw_document: UploadFile,
            background_tasks: BackgroundTasks,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> CreateDocumentResponse:
        temp_path: Optional[Path] = None
        object_name: Optional[str] = None
        file_hash: Optional[str] = None

        logger.info(
            "Document creation initiated",
            extra={
                "document_filename": raw_document.filename,
                "content_type": raw_document.content_type,
                "user_id": user.id
            }
        )

        try:
            try:
                await self._create_document_service_request_validator.validate_create_document_request(
                    raw_document=raw_document,
                    create_document_request=create_document_request
                )
                document_mime_type: DocumentMimeType = (
                    self._create_document_service_utils.get_document_mime_type(
                        raw_document=raw_document
                    )
                )
                logger.info(
                    "Document validation completed",
                    extra={
                        "document_mime_type": document_mime_type.value
                    }
                )

            except Exception as e:
                raise CreateDocumentValidationException(f"Document validation failed: {e}") from e

            if self._create_document_service_settings.deduplication_enabled:
                file_hash = await self._create_document_service_utils.compute_file_hash(raw_document)
                if await self._is_duplicate(file_hash):
                    raise CreateDocumentValidationException(
                        "Duplicate document detected. This file was recently uploaded."
                    )

            temp_path = await self._save_temp_file_streaming(raw_document)
            file_size = temp_path.stat().st_size

            try:
                await raw_document.seek(0)
                object_name = await self._document_storage.upload_document(
                    file=raw_document
                )
                logger.info(
                    "Document uploaded to storage",
                    extra={
                        "object_name": object_name,
                        "size_bytes": file_size
                    }
                )

            except DocumentStorageException as e:
                raise CreateDocumentUploadException(f"Failed to upload document to storage: {e}") from e

            document = Document(
                chat_id=create_document_request.chat_id,
                name=raw_document.filename,
                mime_type=document_mime_type,
                status=DocumentStatus.uploaded,
                storage_url=object_name,
                file_size_bytes=file_size,
                processing_started_at=datetime.now(timezone.utc),
                created_by=user.id,
                created_at=datetime.now(timezone.utc)
            )

            try:
                database_document = await self._document_repository.create_document(
                    document=document,
                    database_session=database_session
                )
                await database_session.commit()
                logger.info(
                    "Document persisted to database",
                    extra={
                        "document_id": database_document.id
                    }
                )

            except DatabaseException as e:
                await self._cleanup_storage(object_name)
                raise CreateDocumentPersistenceException(f"Failed to persist document to database: {e}") from e

            if self._create_document_service_settings.deduplication_enabled and file_hash:
                await self._register_hash(file_hash)

            background_tasks.add_task(
                self._process_document_background,
                document=database_document,
                local_file_path=temp_path,
            )

            logger.info(
                "Document creation completed",
                extra={
                    "document_id": database_document.id,
                    "status": database_document.status.value
                }
            )

            return CreateDocumentResponse.model_validate(database_document)

        except (
                CreateDocumentValidationException,
                CreateDocumentUploadException,
                CreateDocumentPersistenceException
        ):
            if temp_path and temp_path.exists():
                await self._cleanup_temp_file(temp_path)
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during document creation",
                extra={
                    "document_filename": raw_document.filename
                }
            )
            if temp_path and temp_path.exists():
                await self._cleanup_temp_file(temp_path)
            raise CreateDocumentServiceException(f"Document creation failed: {e}") from e

    async def _is_duplicate(
            self,
            file_hash: str
    ) -> bool:
        now = datetime.now(timezone.utc)
        cutoff_seconds = self._create_document_service_settings.deduplication_window_hours * 3600

        async with self._deduplication_lock:
            self._recent_hashes = {
                h: ts
                for h, ts in self._recent_hashes.items()
                if (now - ts).total_seconds() < cutoff_seconds
            }
            return file_hash in self._recent_hashes

    async def _register_hash(
            self,
            file_hash: str
    ) -> None:
        async with self._deduplication_lock:
            self._recent_hashes[file_hash] = datetime.now(timezone.utc)

    async def _save_temp_file_streaming(
            self,
            file: UploadFile
    ) -> Path:
        try:
            temp_dir = Path(tempfile.gettempdir()) / self._create_document_service_settings.temp_dir_prefix
            temp_dir.mkdir(parents=True, exist_ok=True)

            temp_path = temp_dir / f"{uuid.uuid4().hex}_{file.filename}"
            chunk_size = self._create_document_service_settings.chunk_size_bytes

            await file.seek(0)

            def write_chunks():
                with open(temp_path, "wb") as f:
                    while True:
                        chunk = file.file.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)

            await asyncio.to_thread(write_chunks)
            await file.seek(0)

            logger.debug(
                "Temporary file saved",
                extra={
                    "path": str(temp_path),
                    "size_bytes": temp_path.stat().st_size
                }
            )

            return temp_path

        except Exception as e:
            logger.exception("Failed to save temporary file")
            raise IOError(f"Failed to save temporary file: {e}") from e

    async def _cleanup_temp_file(
            self,
            temp_path: Path
    ) -> None:
        try:
            await asyncio.to_thread(temp_path.unlink)
            logger.debug(
                "Temporary file deleted",
                extra={
                    "path": str(temp_path)
                }
            )
        except Exception as e:
            logger.error(
                "Failed to delete temporary file",
                extra={
                    "path": str(temp_path),
                    "error": str(e)
                }
            )

    async def _cleanup_storage(
            self,
            object_name: str
    ) -> None:
        try:
            await self._document_storage.delete_document(object_name)
            logger.info(
                "Compensating action: document deleted from storage",
                extra={
                    "object_name": object_name
                }
            )
        except Exception as e:
            logger.error(
                "Compensating storage delete failed — manual cleanup required",
                extra={
                    "object_name": object_name,
                    "error": str(e)
                }
            )

    async def _process_document_background(
            self,
            document: Document,
            local_file_path: Path
    ) -> None:
        try:
            logger.info(
                "Background processing initiated",
                extra={
                    "document_id": document.id
                }
            )

            await self._document_ingestion_service.process_document(
                document=document,
                local_file_path=local_file_path,
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
            if local_file_path.exists():
                await self._cleanup_temp_file(local_file_path)
