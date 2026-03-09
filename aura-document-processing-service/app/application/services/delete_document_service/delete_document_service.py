import logging
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.delete_document_service.exceptions.delete_document_service_exception import (
    DeleteDocumentFailedException,
    DeleteDocumentNotFoundException,
    DeleteDocumentServiceException,
    DeleteDocumentUnauthorizedException,
    DeleteFragmentsFailedException
)
from app.application.services.delete_document_service.interfaces.delete_document_service_interface import (
    DeleteDocumentServiceInterface
)
from app.domain.models.document import Document
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
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

_ADMIN_ROLES = {"admin", "superadmin"}


class DeleteDocumentService(DeleteDocumentServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            document_storage: DocumentStorageInterface
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._document_storage = document_storage

    async def soft_delete_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> None:
        logger.info(
            "Soft delete document initiated",
            extra={
                "document_id": document_id,
                "user_id": user.id
            }
        )

        try:
            document = await self._get_document_or_raise(
                document_id=document_id,
                database_session=database_session
            )
            self._authorize_admin_or_raise(
                document=document,
                user=user
            )
            await self._soft_delete_fragments_by_document_id(
                document_id=document_id,
                user_id=user.id,
                database_session=database_session
            )
            await self._soft_delete_document_by_id(
                document_id=document_id,
                user_id=user.id,
                database_session=database_session
            )

            logger.info(
                "Soft delete document completed",
                extra={
                    "document_id": document_id,
                    "user_id": user.id
                }
            )

        except (
                DeleteDocumentNotFoundException,
                DeleteDocumentUnauthorizedException,
                DeleteFragmentsFailedException,
                DeleteDocumentFailedException
        ):
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during soft delete document",
                extra={
                    "document_id": document_id
                }
            )
            raise DeleteDocumentServiceException(
                f"Unexpected error during soft delete of document {document_id}"
            ) from e

    async def soft_delete_documents_by_chat(
            self,
            chat_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> None:
        logger.info(
            "Soft delete documents by chat initiated",
            extra={
                "chat_id": chat_id,
                "user_id": user.id
            }
        )

        try:
            documents = await self._get_documents_by_chat_or_raise(
                chat_id=chat_id,
                database_session=database_session
            )
            self._authorize_owner_or_admin_or_raise(
                documents=documents,
                user=user,
                chat_id=chat_id
            )

            for document in documents:
                await self._soft_delete_fragments_by_document_id(
                    document_id=document.id,
                    user_id=user.id,
                    database_session=database_session
                )
                await self._soft_delete_document_by_id(
                    document_id=document.id,
                    user_id=user.id,
                    database_session=database_session
                )

            logger.info(
                "Soft delete documents by chat completed",
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "document_count": len(documents)
                }
            )

        except (
                DeleteDocumentNotFoundException,
                DeleteDocumentUnauthorizedException,
                DeleteFragmentsFailedException,
                DeleteDocumentFailedException
        ):
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during soft delete documents by chat",
                extra={
                    "chat_id": chat_id
                }
            )
            raise DeleteDocumentServiceException(
                f"Unexpected error during soft delete of documents for chat {chat_id}"
            ) from e

    async def hard_delete_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> None:
        logger.info(
            "Hard delete document initiated",
            extra={
                "document_id": document_id,
                "user_id": user.id
            }
        )

        try:
            document = await self._get_document_or_raise(
                document_id=document_id,
                database_session=database_session
            )
            self._authorize_admin_or_raise(
                document=document,
                user=user
            )
            await self._hard_delete_fragments_by_document_id(
                document_id=document_id,
                database_session=database_session
            )
            await self._hard_delete_document_by_id(
                document_id=document_id,
                database_session=database_session
            )
            await self._delete_document_from_storage(
                storage_url=document.storage_url
            )

            logger.info(
                "Hard delete document completed",
                extra={
                    "document_id": document_id,
                    "user_id": user.id
                }
            )

        except (
                DeleteDocumentNotFoundException,
                DeleteDocumentUnauthorizedException,
                DeleteFragmentsFailedException,
                DeleteDocumentFailedException
        ):
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during hard delete document",
                extra={
                    "document_id": document_id
                }
            )
            raise DeleteDocumentServiceException(
                f"Unexpected error during hard delete of document {document_id}"
            ) from e

    async def hard_delete_documents_by_chat(
            self,
            chat_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> None:
        logger.info(
            "Hard delete documents by chat initiated",
            extra={
                "chat_id": chat_id,
                "user_id": user.id
            }
        )

        try:
            documents = await self._get_documents_by_chat_or_raise(
                chat_id=chat_id,
                database_session=database_session
            )
            self._authorize_admin_or_raise_bulk(
                user=user,
                chat_id=chat_id
            )

            for document in documents:
                await self._hard_delete_fragments_by_document_id(
                    document_id=document.id,
                    database_session=database_session
                )
                await self._hard_delete_document_by_id(
                    document_id=document.id,
                    database_session=database_session
                )
                await self._delete_document_from_storage(
                    storage_url=document.storage_url
                )

            logger.info(
                "Hard delete documents by chat completed",
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "document_count": len(documents)
                }
            )

        except (
                DeleteDocumentNotFoundException,
                DeleteDocumentUnauthorizedException,
                DeleteFragmentsFailedException,
                DeleteDocumentFailedException
        ):
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during hard delete documents by chat",
                extra={
                    "chat_id": chat_id
                }
            )
            raise DeleteDocumentServiceException(
                f"Unexpected error during hard delete of documents for chat {chat_id}"
            ) from e

    async def _get_document_or_raise(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> Document:
        document: Optional[Document] = await self._document_repository.get_document_by_id(
            document_id=document_id,
            database_session=database_session
        )

        if document is None:
            logger.warning(
                "Document not found",
                extra={
                    "document_id": document_id
                }
            )
            raise DeleteDocumentNotFoundException(f"Document {document_id} not found")

        return document

    async def _get_documents_by_chat_or_raise(
            self,
            chat_id: int,
            database_session: AsyncSession
    ) -> List[Document]:
        documents: List[Document] = await self._document_repository.get_documents_by_chat_id(
            chat_id=chat_id,
            database_session=database_session
        )

        if not documents:
            logger.warning(
                "No documents found for chat",
                extra={
                    "chat_id": chat_id
                }
            )
            raise DeleteDocumentNotFoundException(f"No documents found for chat {chat_id}")

        return documents

    @staticmethod
    def _authorize_admin_or_raise(
            document: Document,
            user: AuthenticationResponse
    ) -> None:
        if not any(role in user.roles for role in _ADMIN_ROLES):
            logger.warning(
                "Unauthorized delete attempt",
                extra={
                    "document_id": document.id,
                    "user_id": user.id,
                    "user_roles": list(user.roles)
                }
            )
            raise DeleteDocumentUnauthorizedException(
                f"User {user.id} is not authorized to delete document {document.id}"
            )

    @staticmethod
    def _authorize_admin_or_raise_bulk(
            user: AuthenticationResponse,
            chat_id: int
    ) -> None:
        if not any(role in user.roles for role in _ADMIN_ROLES):
            logger.warning(
                "Unauthorized bulk delete attempt",
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "user_roles": list(user.roles)
                }
            )
            raise DeleteDocumentUnauthorizedException(
                f"User {user.id} is not authorized to delete documents for chat {chat_id}"
            )

    @staticmethod
    def _authorize_owner_or_admin_or_raise(
            documents: List[Document],
            user: AuthenticationResponse,
            chat_id: int
    ) -> None:
        if any(role in user.roles for role in _ADMIN_ROLES):
            return

        unauthorized = [
            doc.id for doc in documents
            if doc.created_by != user.id
        ]

        if unauthorized:
            logger.warning(
                "Unauthorized soft delete by chat attempt",
                extra={
                    "chat_id": chat_id,
                    "user_id": user.id,
                    "unauthorized_document_ids": unauthorized
                }
            )
            raise DeleteDocumentUnauthorizedException(
                f"User {user.id} is not authorized to delete documents {unauthorized} in chat {chat_id}"
            )

    async def _hard_delete_fragments_by_document_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> None:
        try:
            await self._fragment_repository.hard_delete_fragments_by_document_id(
                document_id=document_id,
                database_session=database_session
            )
            logger.info(
                "Fragments hard deleted",
                extra={
                    "document_id": document_id
                }
            )

        except Exception as e:
            raise DeleteFragmentsFailedException(
                f"Failed to hard delete fragments for document {document_id}"
            ) from e

    async def _soft_delete_fragments_by_document_id(
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
            logger.info(
                "Fragments soft deleted",
                extra={
                    "document_id": document_id
                }
            )

        except Exception as e:
            raise DeleteFragmentsFailedException(
                f"Failed to soft delete fragments for document {document_id}"
            ) from e

    async def _hard_delete_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> None:
        try:
            await self._document_repository.hard_delete_document_by_id(
                document_id=document_id,
                database_session=database_session
            )
            logger.info(
                "Document record hard deleted",
                extra={
                    "document_id": document_id
                }
            )

        except Exception as e:
            raise DeleteDocumentFailedException(
                f"Failed to hard delete document record {document_id}"
            ) from e

    async def _soft_delete_document_by_id(
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
            logger.info(
                "Document record soft deleted",
                extra={
                    "document_id": document_id
                }
            )

        except Exception as e:
            raise DeleteDocumentFailedException(
                f"Failed to soft delete document record {document_id}"
            ) from e

    async def _delete_document_from_storage(
            self,
            storage_url: str
    ) -> None:
        try:
            await self._document_storage.delete_document(
                object_name=storage_url
            )
            logger.info(
                "Document deleted from storage",
                extra={
                    "storage_url": storage_url
                }
            )

        except DocumentNotFoundException:
            logger.warning(
                "Document not found in storage — skipping storage delete",
                extra={
                    "storage_url": storage_url
                }
            )

        except DocumentStorageException as e:
            logger.critical(
                "Failed to delete document from storage — manual cleanup required",
                extra={
                    "storage_url": storage_url,
                    "error": str(e)
                }
            )
