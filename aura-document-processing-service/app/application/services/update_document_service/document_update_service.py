import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.update_document_service.exceptions.update_document_service_exception import (
    DocumentNotFoundError,
    DocumentUpdateException
)
from app.application.services.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface
)
from app.domain.dtos.update_document.update_document_request import UpdateDocumentRequest
from app.domain.dtos.update_document.update_document_response import UpdateDocumentResponse
from app.domain.models.document import Document
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)

logger = logging.getLogger(__name__)


class UpdateDocumentService(UpdateDocumentServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface
    ):
        self._document_repository = document_repository

        self._successful_updates = 0
        self._failed_updates = 0
        self._last_health_check: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
            cls,
            document_repository: DocumentRepositoryInterface
    ) -> "UpdateDocumentService":
        return cls(
            document_repository=document_repository
        )

    async def update_document(
            self,
            document_id: int,
            update_document_request: UpdateDocumentRequest,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> UpdateDocumentResponse:
        start_time = time.time()

        logger.info(
            "Starting document update",
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
                    "Document not found for update",
                    extra={
                        "document_id": document_id
                    }
                )
                raise DocumentNotFoundError(f"Document with ID {document_id} not found")

            document.is_active = update_document_request.is_active.lower() == "true"
            document.updated_by = user.id
            document.updated_at = datetime.now(timezone.utc)

            try:
                updated_document: Document = await self._document_repository.update_document(
                    document=document,
                    database_session=database_session
                )

                logger.info(
                    "Document updated in database",
                    extra={
                        "document_id": document_id
                    }
                )

            except Exception as e:
                logger.error(
                    "Failed to update document in database",
                    extra={
                        "document_id": document_id,
                        "error": str(e)
                    }
                )
                raise DocumentUpdateException(f"Failed to update document: {str(e)}") from e

            self._successful_updates += 1

            elapsed = (time.time() - start_time) * 1000

            logger.info(
                "Document update completed successfully",
                extra={
                    "document_id": document_id,
                    "elapsed_ms": round(elapsed, 2)
                }
            )

            return UpdateDocumentResponse.model_validate(updated_document)

        except (
                DocumentNotFoundError,
                DocumentUpdateException
        ):
            self._failed_updates += 1
            raise

        except Exception as e:
            self._failed_updates += 1
            logger.exception(
                "Unexpected error during document update",
                extra={
                    "document_id": document_id
                }
            )
            raise DocumentUpdateException(f"Document update failed: {str(e)}") from e

    def get_metrics(
            self
    ) -> Dict[str, int]:
        return {
            "successful_updates": self._successful_updates,
            "failed_updates": self._failed_updates,
        }
