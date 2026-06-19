import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.services.document.restore_document_service.exceptions.restore_document_service_exception import (
    RestoreDocumentConflictException,
    RestoreDocumentFailedException,
    RestoreDocumentInvalidRequestException,
    RestoreDocumentNotFoundException,
    RestoreDocumentServiceException,
    RestoreFragmentsFailedException,
)
from app.application.services.document.restore_document_service.interfaces.restore_document_service_interface import (
    RestoreDocumentServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)


class RestoreDocumentService(RestoreDocumentServiceInterface):
    """Reverses a soft delete, clearing the delete markers on a document and its fragments.

    The restore operates on the Postgres records only. If the asynchronous purge
    of the external footprint (MinIO object / Neo4j graph) already ran after the
    delete, the binary and graph are not recovered by a restore; the document row
    returns but its file/graph must be regenerated (e.g. via reprocess) when the
    stored object is still available.
    """

    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository

    async def restore_document_manage(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentResponse:
        logger.info(
            "A manage restore for the document was initiated.",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        try:
            if document_id <= 0:
                raise RestoreDocumentInvalidRequestException("The document identifier must be a positive number.")

            document = await self._get_deleted_document_or_raise(document_id, database_session)

            restored = await self._restore(document.id, authenticated_user.id, database_session)

            logger.info(
                "The document was restored successfully.",
                extra={
                    "document_id": document_id,
                    "user_id": authenticated_user.id
                }
            )
            return DocumentResponse.model_validate(restored)

        except (
                RestoreDocumentInvalidRequestException,
                RestoreDocumentNotFoundException,
                RestoreDocumentConflictException,
                UnauthorizedException,
                RestoreFragmentsFailedException,
                RestoreDocumentFailedException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred during the restore.",
                extra={
                    "document_id": document_id
                }
            )
            raise RestoreDocumentServiceException(
                "An unexpected error occurred while restoring the document."
            ) from e

    async def _get_deleted_document_or_raise(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> Document:
        document = await self._document_repository.get_document_by_id_including_deleted(
            document_id=document_id,
            database_session=database_session
        )
        if document is None:
            logger.warning(
                "The document was not found.",
                extra={
                    "document_id": document_id
                }
            )
            raise RestoreDocumentNotFoundException("The document was not found.")
        if document.deleted_at is None:
            logger.info(
                "The document is not deleted; nothing to restore.",
                extra={
                    "document_id": document_id
                }
            )
            raise RestoreDocumentConflictException("The document is not deleted.")
        return document

    async def _restore(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> Document:
        await self._restore_fragments(document_id, user_id, database_session)
        return await self._restore_document(document_id, user_id, database_session)

    async def _restore_fragments(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> None:
        try:
            await self._fragment_repository.restore_fragments_by_document_id(
                document_id=document_id,
                user_id=user_id,
                database_session=database_session
            )
            logger.debug(
                "Fragments were restored.",
                extra={
                    "document_id": document_id
                }
            )
        except Exception as e:
            raise RestoreFragmentsFailedException("Failed to restore fragments for the document.") from e

    async def _restore_document(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> Document:
        try:
            document = await self._document_repository.restore_document_by_id(
                document_id=document_id,
                user_id=user_id,
                database_session=database_session
            )
        except Exception as e:
            raise RestoreDocumentFailedException("Failed to restore the document record.") from e

        if document is None:
            # The document was deleted when first read but vanished before restore
            # (concurrent purge/restore). Treat it as a conflict rather than a 500.
            raise RestoreDocumentConflictException("The document is no longer available to restore.")
        return document
