import logging
import time
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.document_deletion_service.exceptions.document_deletion_service_exception import (
    DocumentNotFoundError,
    DocumentDeletionException,
    FragmentDeletionException
)
from app.application.services.document_deletion_service.interfaces.document_deletion_service_interface import (
    DocumentDeletionServiceInterface
)
from app.domain.models.document import Document
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)

logger = logging.getLogger(__name__)


class DocumentDeletionService(DocumentDeletionServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            document_storage: DocumentStorageInterface
    ):
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._document_storage = document_storage

        self._hard_deletes = 0
        self._soft_deletes = 0
        self._failed_deletes = 0
        self._fragment_deletions = 0
        self._storage_deletions = 0
        self._storage_deletion_errors = 0
        self._last_health_check: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
            cls,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            document_storage: DocumentStorageInterface
    ) -> "DocumentDeletionService":
        return cls(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            document_storage=document_storage
        )

    async def hard_delete_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> None:
        start_time = time.time()

        logger.info(
            "Starting hard delete",
            extra={
                "document_id": document_id,
                "user_id": user.id
            }
        )

        try:
            document: Optional[Document] = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=database_session
            )

            if document is None:
                logger.warning(
                    "Document not found for deletion",
                    extra={
                        "document_id": document_id
                    }
                )
                raise DocumentNotFoundError(f"Document with ID {document_id} not found")

            document_path = document.path

            try:
                await self._fragment_repository.hard_delete_fragments_by_document_id(
                    document_id=document_id,
                    database_session=database_session
                )

                self._fragment_deletions += 1

                logger.info(
                    "Fragments deleted",
                    extra={
                        "document_id": document_id
                    }
                )

            except Exception as e:
                logger.error(
                    "Failed to delete fragments",
                    extra={
                        "document_id": document_id,
                        "error": str(e)
                    }
                )
                raise FragmentDeletionException(f"Failed to delete fragments: {str(e)}") from e

            try:
                await self._document_repository.hard_delete_document_by_id(
                    document_id=document_id,
                    database_session=database_session
                )

                logger.info(
                    "Document deleted from database",
                    extra={
                        "document_id": document_id
                    }
                )

            except Exception as e:
                logger.error(
                    "Failed to delete document from database",
                    extra={
                        "document_id": document_id,
                        "error": str(e)
                    }
                )
                raise DocumentDeletionException(f"Failed to delete document from database: {str(e)}") from e

            try:
                await self._document_storage.delete_document(
                    object_name=document_path
                )

                self._storage_deletions += 1

                logger.info(
                    "Document deleted from storage",
                    extra={
                        "document_id": document_id,
                        "path": document_path
                    }
                )

            except Exception as e:
                self._storage_deletion_errors += 1
                logger.warning(
                    "Failed to delete document from storage (non-fatal)",
                    extra={
                        "document_id": document_id,
                        "path": document_path,
                        "error": str(e)
                    }
                )

            self._hard_deletes += 1

            elapsed = (time.time() - start_time) * 1000

            logger.info(
                "Hard delete completed successfully",
                extra={
                    "document_id": document_id,
                    "elapsed_ms": round(elapsed, 2)
                }
            )

        except (
                DocumentNotFoundError,
                FragmentDeletionException,
                DocumentDeletionException
        ):
            self._failed_deletes += 1
            raise

        except Exception as e:
            self._failed_deletes += 1
            logger.exception(
                "Unexpected error during hard delete",
                extra={
                    "document_id": document_id
                }
            )
            raise DocumentDeletionException(f"Hard delete failed: {str(e)}") from e

    async def soft_delete_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> None:
        start_time = time.time()

        logger.info(
            "Starting soft delete",
            extra={
                "document_id": document_id,
                "user_id": user.id
            }
        )

        try:
            document: Optional[Document] = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=database_session
            )

            if document is None:
                logger.warning(
                    "Document not found for soft deletion",
                    extra={
                        "document_id": document_id
                    }
                )
                raise DocumentNotFoundError(f"Document with ID {document_id} not found")

            try:
                await self._fragment_repository.soft_delete_fragments_by_document_id(
                    document_id=document_id,
                    user_id=user.id,
                    database_session=database_session
                )

                logger.info(
                    "Fragments soft deleted",
                    extra={
                        "document_id": document_id
                    }
                )

            except Exception as e:
                logger.error(
                    "Failed to soft delete fragments",
                    extra={
                        "document_id": document_id,
                        "error": str(e)
                    }
                )
                raise FragmentDeletionException(f"Failed to soft delete fragments: {str(e)}") from e

            try:
                await self._document_repository.soft_delete_document_by_id(
                    document_id=document_id,
                    user_id=user.id,
                    database_session=database_session
                )

                logger.info(
                    "Document soft deleted",
                    extra={
                        "document_id": document_id
                    }
                )

            except Exception as e:
                logger.error(
                    "Failed to soft delete document",
                    extra={
                        "document_id": document_id,
                        "error": str(e)
                    }
                )
                raise DocumentDeletionException(f"Failed to soft delete document: {str(e)}") from e

            self._soft_deletes += 1

            elapsed = (time.time() - start_time) * 1000

            logger.info(
                "Soft delete completed successfully",
                extra={
                    "document_id": document_id,
                    "elapsed_ms": round(elapsed, 2)
                }
            )

        except (
                DocumentNotFoundError,
                FragmentDeletionException,
                DocumentDeletionException
        ):
            self._failed_deletes += 1
            raise

        except Exception as e:
            self._failed_deletes += 1
            logger.exception(
                "Unexpected error during soft delete",
                extra={
                    "document_id": document_id
                }
            )
            raise DocumentDeletionException(f"Soft delete failed: {str(e)}") from e

    def get_metrics(
            self
    ) -> Dict[str, int]:
        return {
            "hard_deletes": self._hard_deletes,
            "soft_deletes": self._soft_deletes,
            "failed_deletes": self._failed_deletes,
            "fragment_deletions": self._fragment_deletions,
            "storage_deletions": self._storage_deletions,
            "storage_deletion_errors": self._storage_deletion_errors,
        }
