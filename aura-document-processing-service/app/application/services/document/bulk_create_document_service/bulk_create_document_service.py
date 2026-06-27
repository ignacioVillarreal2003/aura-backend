import logging
from typing import Optional

from fastapi import UploadFile

from app.application.services.document.bulk_create_document_service.bulk_create_document_service_settings import (
    BulkCreateDocumentServiceSettings,
)
from app.application.services.document.bulk_create_document_service.exceptions.bulk_create_document_service_exception import (
    BulkCreateDocumentValidationException,
)
from app.application.services.document.bulk_create_document_service.interfaces.bulk_create_document_service_interface import (
    BulkCreateDocumentServiceInterface,
)
from app.application.services.document.create_document_service.exceptions.create_document_service_exception import (
    CreateDocumentServiceException,
)
from app.application.services.document.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.bulk_create_document.bulk_create_document_response import (
    BulkCreateDocumentItem,
    BulkCreateDocumentResponse,
)
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.field_limits import MAX_ERROR_MESSAGE_CHARS
from app.infrastructure.messaging.rabbitmq.exceptions.rabbitmq_manager_exception import RabbitMQPublishException
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface,
)

logger = logging.getLogger(__name__)

_STATUS_CREATED = "created"
_STATUS_FAILED = "failed"


class BulkCreateDocumentService(BulkCreateDocumentServiceInterface):
    """Uploads several documents in a single request by reusing the existing
    single-document creation flow.

    Each file is processed independently and inside its own database session, so
    a failure on one file rolls back only that file and never aborts the rest of
    the batch. The request as a whole succeeds and returns a per-file breakdown;
    the caller inspects it to decide what to retry.
    """

    def __init__(
            self,
            create_document_service: CreateDocumentServiceInterface,
            database_manager: DatabaseManagerInterface,
            bulk_create_document_service_settings: Optional[BulkCreateDocumentServiceSettings] = None,
    ) -> None:
        self._create_document_service = create_document_service
        self._database_manager = database_manager
        self._settings = bulk_create_document_service_settings or BulkCreateDocumentServiceSettings()

    async def bulk_create_documents(
            self,
            create_document_request: CreateDocumentRequest,
            raw_documents: list[UploadFile],
            authenticated_user: AuthenticatedUser,
    ) -> BulkCreateDocumentResponse:
        self._validate_batch(raw_documents)

        logger.info(
            "Bulk document creation was initiated.",
            extra={
                "file_count": len(raw_documents),
                "user_id": authenticated_user.id,
            },
        )

        items: list[BulkCreateDocumentItem] = []
        created = 0
        failed = 0

        for raw_document in raw_documents:
            item = await self._create_one(
                create_document_request=create_document_request,
                raw_document=raw_document,
                authenticated_user=authenticated_user,
            )
            items.append(item)
            if item.status == _STATUS_CREATED:
                created += 1
            else:
                failed += 1

        logger.info(
            "Bulk document creation completed.",
            extra={
                "total": len(raw_documents),
                # 'created'/'failed' are not used as keys: 'created' is a
                # reserved LogRecord attribute (the record timestamp) and would
                # raise KeyError on makeRecord.
                "created_count": created,
                "failed_count": failed,
                "user_id": authenticated_user.id,
            },
        )

        return BulkCreateDocumentResponse(
            total=len(raw_documents),
            created=created,
            failed=failed,
            items=items,
        )

    def _validate_batch(self, raw_documents: list[UploadFile]) -> None:
        if not raw_documents:
            raise BulkCreateDocumentValidationException("No files were provided.")
        if len(raw_documents) > self._settings.max_documents:
            raise BulkCreateDocumentValidationException(
                "Too many files in a single request. "
                f"The maximum is {self._settings.max_documents}.",
                status_code=413,
            )

    async def _create_one(
            self,
            create_document_request: CreateDocumentRequest,
            raw_document: UploadFile,
            authenticated_user: AuthenticatedUser,
    ) -> BulkCreateDocumentItem:
        try:
            # A fresh session per file isolates each document in its own
            # transaction; the context manager rolls it back on failure so a bad
            # file never poisons the session used by the others.
            async with self._database_manager.session() as database_session:
                response = await self._create_document_service.create_document(
                    create_document_request=create_document_request,
                    raw_document=raw_document,
                    database_session=database_session,
                    authenticated_user=authenticated_user,
                )
            return BulkCreateDocumentItem(
                status=_STATUS_CREATED,
                filename=raw_document.filename,
                id=response.id,
                name=response.name,
                mime_type=response.mime_type,
                document_status=response.status,
                file_size_bytes=response.file_size_bytes,
            )
        except (CreateDocumentServiceException, RabbitMQPublishException) as exc:
            logger.warning(
                "A file in a bulk-create request failed.",
                extra={
                    # 'filename' is a reserved LogRecord attribute; use a
                    # non-colliding key.
                    "document_filename": raw_document.filename,
                    "exception_type": type(exc).__name__,
                },
            )
            return self._failed_item(raw_document, str(exc))
        except Exception:
            logger.exception(
                "An unexpected error occurred while creating a file in a bulk-create request.",
                extra={"document_filename": raw_document.filename},
            )
            return self._failed_item(raw_document, "The document could not be created.")

    @staticmethod
    def _failed_item(raw_document: UploadFile, message: str) -> BulkCreateDocumentItem:
        return BulkCreateDocumentItem(
            status=_STATUS_FAILED,
            filename=raw_document.filename,
            error=message[:MAX_ERROR_MESSAGE_CHARS],
        )
