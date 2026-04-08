import asyncio
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.document.create_document_service.create_document_service_authorizer import (
    CreateDocumentServiceAuthorizer
)
from app.application.services.document.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings
)
from app.application.services.document.create_document_service.create_document_service_utils import (
    CreateDocumentServiceUtils
)
from app.application.services.document.create_document_service.create_document_service_validator import (
    CreateDocumentServiceValidator
)
from app.application.services.document.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentPersistenceException,
    CreateDocumentServiceException,
    CreateDocumentUnauthorizedException,
    CreateDocumentUploadException,
    CreateDocumentValidationException
)
from app.application.services.document.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface
)
from app.domain.constants.document.document_mime_type import DocumentMimeType
from app.domain.constants.document.document_status import DocumentStatus
from app.domain.constants.user.user_roles import ALL_ROLES
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.document.create_document.create_document_response import CreateDocumentResponse
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import DocumentIngestionCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.models.document import Document
from app.infrastructure.messaging.rabbitmq.exceptions.rabbitmq_manager_exception import RabbitMQPublishException
from app.infrastructure.messaging.rabbitmq.interfaces.rabbitmq_manager_interface import RabbitMQManagerInterface
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
            rabbitmq_manager: RabbitMQManagerInterface,
            create_document_service_settings: Optional[CreateDocumentServiceSettings] = None,
    ) -> None:
        self._document_repository = document_repository
        self._document_storage = document_storage
        self._rabbitmq_manager = rabbitmq_manager
        self._settings = create_document_service_settings or CreateDocumentServiceSettings()

        self._validator = CreateDocumentServiceValidator(
            create_document_service_settings=self._settings
        )
        self._authorizer = CreateDocumentServiceAuthorizer()
        self._utils = CreateDocumentServiceUtils(
            create_document_service_settings=self._settings
        )

        self._deduplication_lock = asyncio.Lock()
        self._recent_hashes: dict[str, datetime] = {}

    async def create_document(
            self,
            create_document_request: CreateDocumentRequest,
            raw_document: UploadFile,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> CreateDocumentResponse:
        temp_path: Optional[Path] = None
        object_name: Optional[str] = None

        logger.info(
            "Document creation was initiated.",
            extra={
                "document_filename": raw_document.filename,
                "content_type": raw_document.content_type,
                "user_id": authenticated_user.id
            }
        )

        try:
            self._require_permissions(authenticated_user)
            self._authorizer.require_roles(
                authenticated_user=authenticated_user,
                allowed_roles=ALL_ROLES
            )

            try:
                await self._validator.validate_create_document_request(
                    raw_document=raw_document,
                    create_document_request=create_document_request
                )
                document_mime_type: DocumentMimeType = self._utils.get_document_mime_type(
                    raw_document=raw_document
                )
            except Exception as e:
                raise CreateDocumentValidationException("The document could not be validated.") from e

            file_hash: Optional[str] = None
            if self._settings.deduplication_enabled:
                file_hash = await self._utils.compute_file_hash(raw_document)
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
                    "The document was uploaded to storage.",
                    extra={
                        "object_name": object_name,
                        "size_bytes": file_size
                    }
                )
            except DocumentStorageException as e:
                raise CreateDocumentUploadException("Failed to upload the document to storage.") from e

            now = datetime.now(timezone.utc)
            document = Document(
                chat_id=create_document_request.chat_id,
                name=raw_document.filename,
                mime_type=document_mime_type,
                status=DocumentStatus.uploaded,
                storage_url=object_name,
                file_size_bytes=file_size,
                processing_started_at=now,
                created_by=authenticated_user.id,
                created_at=now
            )

            try:
                database_document = await self._document_repository.create_document(
                    document=document,
                    database_session=database_session
                )
                await database_session.commit()
                logger.info(
                    "The document was saved to the database.",
                    extra={
                        "document_id": database_document.id
                    }
                )
            except DatabaseException as e:
                await self._cleanup_storage(object_name)
                raise CreateDocumentPersistenceException("Failed to save the document to the database.") from e

            if self._settings.deduplication_enabled and file_hash:
                await self._register_hash(file_hash)

            await self._cleanup_temp_file(temp_path)
            temp_path = None

            command = DocumentIngestionCommand(
                document_id=database_document.id,
                storage_url=object_name,
                filename=raw_document.filename,
                mime_type=raw_document.content_type or "",
                created_by=authenticated_user.id,
                prefer_docling=create_document_request.prefer_docling
            )
            envelope = MessageEnvelope.wrap(command)

            try:
                await self._rabbitmq_manager.publish(
                    routing_key=self._rabbitmq_manager.settings.document_ingestion_queue,
                    body=envelope.to_bytes(),
                    headers={
                        "message_id": envelope.message_id
                    }
                )
            except Exception as e:
                raise RabbitMQPublishException("Failed to enqueue the document for ingestion.") from e

            logger.info(
                "Document creation completed and the ingestion message was published.",
                extra={
                    "document_id": database_document.id,
                    "status": database_document.status.value,
                    "message_id": envelope.message_id
                }
            )

            return CreateDocumentResponse.model_validate(database_document)

        except (
                CreateDocumentUnauthorizedException,
                CreateDocumentValidationException,
                CreateDocumentUploadException,
                CreateDocumentPersistenceException
        ):
            if temp_path is not None:
                await self._cleanup_temp_file(temp_path)
            raise

        except Exception as e:
            logger.exception(
                "An unexpected error occurred during document creation.",
                extra={
                    "document_filename": raw_document.filename
                }
            )
            if temp_path is not None:
                await self._cleanup_temp_file(temp_path)
            raise CreateDocumentServiceException("Document creation failed.") from e

    def _require_permissions(
            self,
            authenticated_user: AuthenticatedUser
    ) -> None:
        self._authorizer.require_permissions(authenticated_user)

    async def _is_duplicate(
            self,
            file_hash: str
    ) -> bool:
        now = datetime.now(timezone.utc)
        cutoff_seconds = self._settings.deduplication_window_hours * 3600

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
            temp_dir = Path(tempfile.gettempdir()) / self._settings.temp_dir_prefix
            temp_dir.mkdir(parents=True, exist_ok=True)

            safe_name = Path(file.filename).name
            temp_path = temp_dir / f"{uuid.uuid4().hex}_{safe_name}"
            chunk_size = self._settings.chunk_size_bytes

            await file.seek(0)

            def _write_chunks() -> None:
                with open(temp_path, "wb") as f:
                    while True:
                        chunk = file.file.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)

            await asyncio.to_thread(_write_chunks)
            await file.seek(0)

            logger.debug(
                "The temporary file was saved.",
                extra={
                    "path": str(temp_path),
                    "size_bytes": temp_path.stat().st_size
                }
            )
            return temp_path

        except Exception as e:
            logger.exception("Failed to save the temporary file.")
            raise IOError("Failed to save the temporary file.") from e

    async def _cleanup_temp_file(
            self,
            temp_path: Path
    ) -> None:
        try:
            if await asyncio.to_thread(temp_path.exists):
                await asyncio.to_thread(temp_path.unlink)
                logger.debug(
                    "The temporary file was deleted.",
                    extra={
                        "path": str(temp_path)
                    }
                )
        except Exception as e:
            logger.warning(
                "Failed to delete the temporary file.",
                extra={
                    "path": str(temp_path),
                    "exception_type": type(e).__name__
                }
            )

    async def _cleanup_storage(
            self,
            object_name: str
    ) -> None:
        try:
            await self._document_storage.delete_document(object_name)
            logger.info(
                "A compensating action removed the document from storage.",
                extra={
                    "object_name": object_name
                }
            )
        except Exception as e:
            logger.error(
                "The compensating storage delete failed. Manual cleanup may be required.",
                extra={
                    "object_name": object_name,
                    "exception_type": type(e).__name__
                }
            )


async def get_create_document_service(
        request: Request
) -> CreateDocumentServiceInterface:
    try:
        return request.app.state.create_document_service
    except AttributeError:
        logger.error("CreateDocumentService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CreateDocumentService is not registered on the application state."
        )
