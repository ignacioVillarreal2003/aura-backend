import asyncio
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.services.document.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings
)
from app.application.services.document.create_document_service.create_document_service_utils import (
    CreateDocumentServiceUtils
)
from app.application.services.document.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentInvalidException,
    CreateDocumentPersistenceException,
    CreateDocumentServiceException,
    CreateDocumentSizeExceededException,
    CreateDocumentUnsupportedTypeException,
    CreateDocumentUploadException,
    CreateDocumentValidationException,
)
from app.application.services.document.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface
)
from app.domain.constants.document.document_mime_type import DocumentMimeType
from app.domain.constants.document.document_status import DocumentStatus
from app.domain.constants.document_processing_permissions import DocumentProcessingPermissions
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.document.create_document.create_document_response import CreateDocumentResponse
from app.infrastructure.messaging.rabbitmq.dtos.commands.document_ingestion_command import DocumentIngestionCommand
from app.infrastructure.messaging.rabbitmq.dtos.envelope.message_envelope import MessageEnvelope
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.models.document import Document
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_exception import RabbitMQPublishException
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_interface import RabbitMQManagerInterface
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.database_exceptions import DatabaseException
from app.infrastructure.persistence.storages.document_storage.document_storage_exception import (
    DocumentStorageException
)
from app.infrastructure.persistence.storages.document_storage.document_storage_interface import (
    DocumentStorageInterface
)

logger = logging.getLogger(__name__)


class CreateDocumentService(CreateDocumentServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            document_storage: DocumentStorageInterface,
            rabbitmq_manager: RabbitMQManagerInterface,
            authorizer: Authorizer,
            create_document_service_settings: Optional[CreateDocumentServiceSettings] = None,
    ) -> None:
        self._document_repository = document_repository
        self._document_storage = document_storage
        self._rabbitmq_manager = rabbitmq_manager
        self._settings = create_document_service_settings or CreateDocumentServiceSettings()
        self._authorizer = authorizer
        self._utils = CreateDocumentServiceUtils(
            create_document_service_settings=self._settings
        )

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
            self._authorizer.require_permissions(
                authenticated_user=authenticated_user,
                required_permissions=frozenset({DocumentProcessingPermissions.INGEST_DOCUMENT}),
            )

            try:
                self._validate_file_present(raw_document)
                self._validate_filename(raw_document)
                self._validate_content_type(raw_document)
                self._validate_size(raw_document)
                await self._validate_magic_numbers(raw_document)
                document_mime_type: DocumentMimeType = self._utils.get_document_mime_type(
                    raw_document=raw_document
                )
            except Exception as e:
                raise CreateDocumentValidationException("The document could not be validated.") from e

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
                UnauthorizedException,
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

    @staticmethod
    def _validate_file_present(file: UploadFile) -> None:
        if file is None:
            raise CreateDocumentValidationException("No file was provided.")
        if not file.filename:
            raise CreateDocumentValidationException("The file must have a filename.")

    @staticmethod
    def _validate_filename(file: UploadFile) -> None:
        filename = file.filename
        if ".." in filename or "/" in filename or "\\" in filename:
            raise CreateDocumentInvalidException(
                "The filename contains invalid characters. Path separators are not allowed."
            )
        if "\x00" in filename:
            raise CreateDocumentInvalidException("The filename contains null bytes.")
        if len(filename) > 255:
            raise CreateDocumentInvalidException("The filename is too long. The maximum length is 255 characters.")

    def _validate_content_type(self, file: UploadFile) -> None:
        content_type = file.content_type
        if not content_type:
            raise CreateDocumentInvalidException("The file content type was not provided.")
        if not self._settings.is_content_type_allowed(content_type):
            raise CreateDocumentUnsupportedTypeException(
                "This file type is not supported. Please upload a supported document format."
            )

    def _validate_size(self, file: UploadFile) -> None:
        file_size = self._get_file_size(file)
        if file_size is None:
            raise CreateDocumentInvalidException("The file size could not be determined.")
        if file_size < self._settings.min_file_size_bytes:
            raise CreateDocumentInvalidException("The file is smaller than the minimum allowed size.")
        if file_size > self._settings.max_file_size_bytes:
            raise CreateDocumentSizeExceededException("The file is larger than the maximum allowed size.")

    async def _validate_magic_numbers(self, file: UploadFile) -> None:
        content_type = file.content_type
        magic_numbers = self._settings.get_magic_numbers(content_type)
        if not magic_numbers:
            return
        try:
            await file.seek(0)
            header = await file.read(8)
            await file.seek(0)
            if not header:
                raise CreateDocumentInvalidException("The file header could not be read.")
            if not any(header.startswith(magic) for magic in magic_numbers):
                raise CreateDocumentInvalidException(
                    "The file content does not match the declared type. The file may be invalid or mislabeled."
                )
        except CreateDocumentInvalidException:
            raise
        except Exception as e:
            raise CreateDocumentInvalidException("Failed to validate the file content.") from e

    @staticmethod
    def _get_file_size(file: UploadFile) -> Optional[int]:
        file_size = getattr(file, "size", None)
        if file_size is not None:
            return file_size
        try:
            current_pos = file.file.tell()
            file.file.seek(0, 2)
            size = file.file.tell()
            file.file.seek(current_pos)
            return size
        except Exception:
            return None

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
