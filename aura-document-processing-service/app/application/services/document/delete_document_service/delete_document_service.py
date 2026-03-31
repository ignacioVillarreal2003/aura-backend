import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Request, status

from app.application.services.document.delete_document_service.exceptions.delete_document_service_exception import (
    DeleteDocumentFailedException,
    DeleteDocumentInvalidRequestException,
    DeleteDocumentNotFoundException,
    DeleteDocumentServiceException,
    DeleteDocumentStorageException,
    DeleteDocumentUnauthorizedException,
    DeleteFragmentsFailedException
)
from app.application.services.document.delete_document_service.delete_document_service_authorizer import (
    DeleteDocumentServiceAuthorizer,
)
from app.application.services.document.delete_document_service.delete_document_service_settings import (
    DeleteDocumentServiceSettings,
)
from app.application.services.document.delete_document_service.delete_document_service_validator import (
    DeleteDocumentServiceValidator,
)
from app.application.services.document.delete_document_service.interfaces.delete_document_service_interface import (
    DeleteDocumentServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.user.user_roles import ADMIN_ROLES, ALL_ROLES
from app.domain.models.document import Document
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)
from app.infrastructure.persistence.storages.document_storage.exceptions.document_storage_exception import (
    DocumentNotFoundException,
    DocumentStorageException
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)

logger = logging.getLogger(__name__)


class DeleteDocumentService(DeleteDocumentServiceInterface):
    _KNOWN_EXCEPTIONS = (
        DeleteDocumentInvalidRequestException,
        DeleteDocumentNotFoundException,
        DeleteDocumentUnauthorizedException,
        DeleteFragmentsFailedException,
        DeleteDocumentFailedException,
        DeleteDocumentStorageException
    )

    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            document_storage: DocumentStorageInterface,
            delete_document_service_settings: Optional[DeleteDocumentServiceSettings] = None,
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._document_storage = document_storage
        self._settings = delete_document_service_settings or DeleteDocumentServiceSettings()
        self._validator = DeleteDocumentServiceValidator(self._settings)
        self._authorizer = DeleteDocumentServiceAuthorizer()

    async def soft_delete_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> None:
        logger.info(
            "Soft delete document initiated",
            extra={"document_id": document_id, "user_id": authenticated_user.id}
        )

        try:
            self._validator.validate_document_id(document_id)
            self._authorizer.require_permissions(authenticated_user)
            self._authorizer.require_roles(authenticated_user=authenticated_user, allowed_roles=ADMIN_ROLES)

            document = await self._get_document_or_raise(document_id, database_session)

            await self._soft_delete_fragments(document.id, authenticated_user.id, database_session)
            await self._soft_delete_document(document.id, authenticated_user.id, database_session)

            logger.info(
                "Soft delete document completed",
                extra={"document_id": document_id, "user_id": authenticated_user.id}
            )

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception("Unexpected error during soft delete document",
                             extra={"document_id": document_id})
            raise DeleteDocumentServiceException(
                f"Unexpected error during soft delete of document {document_id}"
            ) from e

    async def soft_delete_documents_by_chat(
            self,
            chat_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> None:
        logger.info(
            "Soft delete documents by chat initiated",
            extra={"chat_id": chat_id, "user_id": authenticated_user.id}
        )

        try:
            self._validator.validate_chat_id(chat_id)
            self._authorizer.require_permissions(authenticated_user)
            self._authorizer.require_roles(authenticated_user=authenticated_user, allowed_roles=ALL_ROLES)

            documents = await self._get_documents_by_chat(chat_id, database_session)
            self._validator.validate_documents_count(len(documents))

            if not documents:
                logger.info("No documents found for chat — nothing to delete", extra={"chat_id": chat_id})
                return

            is_admin = authenticated_user.has_any_role(ADMIN_ROLES)
            if not is_admin:
                documents = self._filter_owned_or_raise(documents, authenticated_user, chat_id)

            for document in documents:
                await self._soft_delete_fragments(document.id, authenticated_user.id, database_session)
                await self._soft_delete_document(document.id, authenticated_user.id, database_session)

            logger.info(
                "Soft delete documents by chat completed",
                extra={"chat_id": chat_id, "user_id": authenticated_user.id, "document_count": len(documents)}
            )

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception("Unexpected error during soft delete documents by chat", extra={"chat_id": chat_id})
            raise DeleteDocumentServiceException(
                f"Unexpected error during soft delete of documents for chat {chat_id}"
            ) from e

    async def hard_delete_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> None:
        logger.info(
            "Hard delete document initiated",
            extra={"document_id": document_id, "user_id": authenticated_user.id}
        )

        try:
            self._validator.validate_document_id(document_id)
            self._authorizer.require_permissions(authenticated_user)
            self._authorizer.require_roles(authenticated_user=authenticated_user, allowed_roles=ADMIN_ROLES)

            document = await self._get_document_or_raise(document_id, database_session)

            await self._hard_delete_fragments(document.id, database_session)
            await self._hard_delete_document(document.id, database_session)

            await self._delete_from_storage(document.storage_url)

            logger.info(
                "Hard delete document completed",
                extra={"document_id": document_id, "user_id": authenticated_user.id}
            )

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception("Unexpected error during hard delete document",
                             extra={"document_id": document_id})
            raise DeleteDocumentServiceException(
                f"Unexpected error during hard delete of document {document_id}"
            ) from e

    async def hard_delete_documents_by_chat(
            self,
            chat_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> None:
        logger.info(
            "Hard delete documents by chat initiated",
            extra={"chat_id": chat_id, "user_id": authenticated_user.id}
        )

        try:
            self._validator.validate_chat_id(chat_id)
            self._authorizer.require_permissions(authenticated_user)
            self._authorizer.require_roles(authenticated_user=authenticated_user, allowed_roles=ADMIN_ROLES)

            documents = await self._get_documents_by_chat(chat_id, database_session)
            self._validator.validate_documents_count(len(documents))

            if not documents:
                logger.info("No documents found for chat — nothing to delete", extra={"chat_id": chat_id})
                return

            for document in documents:
                await self._hard_delete_fragments(document.id, database_session)
                await self._hard_delete_document(document.id, database_session)
                await self._delete_from_storage(document.storage_url)

            logger.info(
                "Hard delete documents by chat completed",
                extra={"chat_id": chat_id, "user_id": authenticated_user.id, "document_count": len(documents)}
            )

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception("Unexpected error during hard delete documents by chat", extra={"chat_id": chat_id})
            raise DeleteDocumentServiceException(
                f"Unexpected error during hard delete of documents for chat {chat_id}"
            ) from e

    @staticmethod
    def _filter_owned_or_raise(
            documents: list[Document],
            authenticated_user: AuthenticatedUser,
            chat_id: int
    ) -> list[Document]:
        owned = [doc for doc in documents if doc.created_by == authenticated_user.id]

        if not owned:
            unauthorized_ids = [doc.id for doc in documents]
            logger.warning(
                "User attempted to delete documents they do not own",
                extra={
                    "chat_id": chat_id,
                    "user_id": authenticated_user.id,
                    "document_ids": unauthorized_ids
                }
            )
            raise DeleteDocumentUnauthorizedException(
                f"User {authenticated_user.id} does not own any documents in chat {chat_id}"
            )

        not_owned = [doc.id for doc in documents if doc.created_by != authenticated_user.id]
        if not_owned:
            logger.info(
                "User role: skipping documents not owned by user",
                extra={"chat_id": chat_id, "user_id": authenticated_user.id, "skipped_document_ids": not_owned}
            )

        return owned

    async def _get_document_or_raise(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> Document:
        document = await self._document_repository.get_document_by_id(
            document_id=document_id,
            database_session=database_session
        )
        if document is None:
            logger.warning("Document not found", extra={"document_id": document_id})
            raise DeleteDocumentNotFoundException(f"Document {document_id} not found")
        return document

    async def _get_documents_by_chat(
            self,
            chat_id: int,
            database_session: AsyncSession
    ) -> list[Document]:
        return await self._document_repository.get_documents_by_chat_id(
            chat_id=chat_id,
            database_session=database_session
        )

    async def _soft_delete_fragments(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> None:
        try:
            await self._fragment_repository.soft_delete_fragments_by_document_id(
                document_id=document_id,
                user_id=user_id,
                database_session=database_session
            )
            logger.debug("Fragments soft deleted", extra={"document_id": document_id})
        except Exception as e:
            raise DeleteFragmentsFailedException(
                f"Failed to soft delete fragments for document {document_id}"
            ) from e

    async def _hard_delete_fragments(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> None:
        try:
            await self._fragment_repository.hard_delete_fragments_by_document_id(
                document_id=document_id,
                database_session=database_session
            )
            logger.debug("Fragments hard deleted", extra={"document_id": document_id})
        except Exception as e:
            raise DeleteFragmentsFailedException(
                f"Failed to hard delete fragments for document {document_id}"
            ) from e

    async def _soft_delete_document(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> None:
        try:
            await self._document_repository.soft_delete_document_by_id(
                document_id=document_id,
                user_id=user_id,
                database_session=database_session
            )
            logger.debug("Document record soft deleted", extra={"document_id": document_id})
        except Exception as e:
            raise DeleteDocumentFailedException(
                f"Failed to soft delete document record {document_id}"
            ) from e

    async def _hard_delete_document(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> None:
        try:
            await self._document_repository.hard_delete_document_by_id(
                document_id=document_id,
                database_session=database_session
            )
            logger.debug("Document record hard deleted", extra={"document_id": document_id})
        except Exception as e:
            raise DeleteDocumentFailedException(
                f"Failed to hard delete document record {document_id}"
            ) from e

    async def _delete_from_storage(self, storage_url: str) -> None:
        try:
            await self._document_storage.delete_document(object_name=storage_url)
            logger.debug("Document deleted from storage", extra={"storage_url": storage_url})

        except DocumentNotFoundException:
            logger.warning(
                "Document not found in storage — already deleted or never uploaded",
                extra={"storage_url": storage_url}
            )

        except DocumentStorageException as e:
            logger.critical(
                "Failed to delete document from storage after DB record was removed — manual cleanup required",
                extra={"storage_url": storage_url, "error": str(e)}
            )
            raise DeleteDocumentStorageException(
                f"Document DB record deleted but storage cleanup failed for '{storage_url}'. "
                "Manual cleanup required."
            ) from e


async def get_delete_document_service(request: Request) -> DeleteDocumentServiceInterface:
    try:
        return request.app.state.delete_document_service
    except AttributeError:
        logger.error("DeleteDocumentService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DeleteDocumentService not configured"
        )
