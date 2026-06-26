import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.services.document.update_document_service.exceptions.update_document_service_exception import (
    UpdateDocumentFailedException,
    UpdateDocumentInvalidRequestException,
    UpdateDocumentNotFoundException,
    UpdateDocumentServiceException,
)
from app.application.services.document.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.dtos.document.update_document.update_document_request import UpdateDocumentRequest
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)

logger = logging.getLogger(__name__)

_EDITABLE_FIELDS = frozenset({"name"})


class UpdateDocumentService(UpdateDocumentServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
    ) -> None:
        self._document_repository = document_repository

    async def update_document_manage(
            self,
            document_id: int,
            update_document_request: UpdateDocumentRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentResponse:
        logger.info(
            "A manage update for the document metadata was initiated.",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        try:
            if document_id <= 0:
                raise UpdateDocumentInvalidRequestException("The document identifier must be a positive number.")

            changes = {
                field: value
                for field, value in update_document_request.model_dump(exclude_unset=True).items()
                if field in _EDITABLE_FIELDS
            }
            if not changes:
                raise UpdateDocumentInvalidRequestException(
                    "At least one field must be provided to update the document.")

            document = await self._get_document_or_raise(document_id, database_session)

            for field, value in changes.items():
                setattr(document, field, value)
            document.updated_by = int(authenticated_user.id)
            document.updated_at = datetime.now(timezone.utc)

            updated_document = await self._persist(document, database_session)

            logger.info(
                "The document metadata was updated successfully.",
                extra={
                    "document_id": document_id,
                    "user_id": authenticated_user.id,
                    "updated_fields": sorted(changes.keys())
                }
            )
            return DocumentResponse.model_validate(updated_document)

        except (
                UpdateDocumentInvalidRequestException,
                UpdateDocumentNotFoundException,
                UnauthorizedException,
                UpdateDocumentFailedException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while updating the document.",
                extra={
                    "document_id": document_id
                }
            )
            raise UpdateDocumentServiceException(
                "An unexpected error occurred while updating the document."
            ) from e

    async def _get_document_or_raise(
            self,
            document_id: int,
            database_session: AsyncSession,
    ) -> Document:
        document = await self._document_repository.get_document_by_id(
            document_id=document_id,
            database_session=database_session,
        )
        if document is None:
            logger.warning(
                "The document was not found.",
                extra={
                    "document_id": document_id
                }
            )
            raise UpdateDocumentNotFoundException("The document was not found.")
        return document

    async def _persist(
            self,
            document: Document,
            database_session: AsyncSession,
    ) -> Document:
        try:
            return await self._document_repository.update_document(
                document=document,
                database_session=database_session,
            )
        except Exception as e:
            raise UpdateDocumentFailedException("Failed to update the document record.") from e
