import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.document.delete_document_service.exceptions.delete_document_service_exception import (
    DeleteDocumentFailedException,
    DeleteDocumentInvalidRequestException,
    DeleteDocumentNotFoundException,
    DeleteDocumentServiceException,
    DeleteFragmentsFailedException
)
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.services.document.delete_document_service.delete_document_service_settings import (
    DeleteDocumentServiceSettings
)
from app.application.services.document.delete_document_service.interfaces.delete_document_service_interface import (
    DeleteDocumentServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.http.chat_membership.chat_membership_provider_interface import (
    ChatMembershipProviderInterface,
)
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class DeleteDocumentService(DeleteDocumentServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            chat_membership_provider: ChatMembershipProviderInterface,
            delete_document_service_settings: Optional[DeleteDocumentServiceSettings] = None
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._chat_membership_provider = chat_membership_provider
        self._settings = delete_document_service_settings or DeleteDocumentServiceSettings()

    async def soft_delete_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> None:
        logger.info(
            "A soft delete for the document was initiated.",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        try:
            if document_id <= 0:
                raise DeleteDocumentInvalidRequestException("The document identifier must be a positive number.")

            document = await self._get_document_or_raise(document_id, database_session)

            await self._require_document_access(document, authenticated_user)

            await self._soft_delete_fragments(document.id, authenticated_user.id, database_session)
            await self._soft_delete_document(document.id, authenticated_user.id, database_session)

            logger.info(
                "The document was soft deleted successfully.",
                extra={
                    "document_id": document_id,
                    "user_id": authenticated_user.id
                }
            )

        except (
                DeleteDocumentInvalidRequestException,
                DeleteDocumentNotFoundException,
                UnauthorizedException,
                DeleteFragmentsFailedException,
                DeleteDocumentFailedException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred during the soft delete.",
                extra={
                    "document_id": document_id
                }
            )
            raise DeleteDocumentServiceException(
                "An unexpected error occurred while soft deleting the document."
            ) from e

    async def soft_delete_documents_by_chat(
            self,
            chat_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> None:
        logger.info(
            "A soft delete for documents in the chat was initiated.",
            extra={
                "chat_id": chat_id,
                "user_id": authenticated_user.id
            }
        )

        try:
            if chat_id <= 0:
                raise DeleteDocumentInvalidRequestException("The chat identifier must be a positive number.")

            membership = await self._chat_membership_provider.get_membership(
                chat_id=chat_id,
                user_id=int(authenticated_user.id),
                authorization_header=get_request_token(),
            )
            if not membership.can_modify:
                logger.warning(
                    "Unauthorized soft delete by chat attempt.",
                    extra={
                        "chat_id": chat_id,
                        "user_id": authenticated_user.id,
                    },
                )
                raise UnauthorizedException(
                    "You are not authorized to delete documents for this chat."
                )

            documents = await self._get_documents_by_chat(chat_id, database_session)
            if len(documents) > self._settings.max_ids_per_operation:
                raise DeleteDocumentInvalidRequestException(
                    "The number of documents exceeds the limit for a single operation."
                )

            if not documents:
                logger.info(
                    "No documents were found for the chat; nothing to delete.",
                    extra={
                        "chat_id": chat_id
                    }
                )
                return

            for document in documents:
                await self._soft_delete_fragments(document.id, authenticated_user.id, database_session)
                await self._soft_delete_document(document.id, authenticated_user.id, database_session)

            logger.info(
                "Documents in the chat were soft deleted successfully.",
                extra={
                    "chat_id": chat_id,
                    "user_id": authenticated_user.id,
                    "document_count": len(documents)
                }
            )

        except (
                DeleteDocumentInvalidRequestException,
                DeleteDocumentNotFoundException,
                UnauthorizedException,
                DeleteFragmentsFailedException,
                DeleteDocumentFailedException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred during soft delete by chat.",
                extra={
                    "chat_id": chat_id
                }
            )
            raise DeleteDocumentServiceException(
                "An unexpected error occurred while soft deleting documents for the chat."
            ) from e

    async def soft_delete_document_admin(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> None:
        logger.info(
            "An admin soft delete for the document was initiated.",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        try:
            if document_id <= 0:
                raise DeleteDocumentInvalidRequestException("The document identifier must be a positive number.")

            document = await self._get_document_or_raise(document_id, database_session)

            await self._soft_delete_fragments(document.id, authenticated_user.id, database_session)
            await self._soft_delete_document(document.id, authenticated_user.id, database_session)

            logger.info(
                "The document was soft deleted successfully by an admin.",
                extra={
                    "document_id": document_id,
                    "user_id": authenticated_user.id
                }
            )

        except (
                DeleteDocumentInvalidRequestException,
                DeleteDocumentNotFoundException,
                UnauthorizedException,
                DeleteFragmentsFailedException,
                DeleteDocumentFailedException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred during the admin soft delete.",
                extra={
                    "document_id": document_id
                }
            )
            raise DeleteDocumentServiceException(
                "An unexpected error occurred while soft deleting the document."
            ) from e

    async def _require_document_access(
            self,
            document,
            authenticated_user: AuthenticatedUser,
    ) -> None:
        if document.chat_id is not None:
            membership = await self._chat_membership_provider.get_membership(
                chat_id=int(document.chat_id),
                user_id=int(authenticated_user.id),
                authorization_header=get_request_token(),
            )
            if membership.can_modify:
                return

        logger.warning(
            "Unauthorized soft delete document attempt.",
            extra={
                "document_id": document.id,
                "user_id": authenticated_user.id,
            },
        )
        raise UnauthorizedException("You are not authorized to delete this document.")

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
            logger.warning(
                "The document was not found.",
                extra={
                    "document_id": document_id
                }
            )
            raise DeleteDocumentNotFoundException("The document was not found.")
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
            logger.debug(
                "Fragments were soft deleted.",
                extra={
                    "document_id": document_id
                }
            )
        except Exception as e:
            raise DeleteFragmentsFailedException("Failed to soft delete fragments for the document.") from e

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
            logger.debug(
                "The document record was soft deleted.",
                extra={
                    "document_id": document_id
                }
            )
        except Exception as e:
            raise DeleteDocumentFailedException("Failed to soft delete the document record.") from e
