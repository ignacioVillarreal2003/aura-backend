import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.update_document_service.exceptions.update_document_service_exception import (
    UpdateDocumentNotFoundException,
    UpdateDocumentUnauthorizedException,
    UpdateDocumentFailedException,
    UpdateDocumentServiceException
)
from app.application.services.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface
)
from app.domain.dtos.update_document_controller.post_process_document_request import PostProcessDocumentRequest
from app.domain.dtos.update_document_controller.post_process_document_response import PostProcessDocumentResponse
from app.domain.models.document import Document
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)

logger = logging.getLogger(__name__)

_ADMIN_ROLES = {"admin", "superadmin"}


class UpdateDocumentService(UpdateDocumentServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface
    ) -> None:
        self._document_repository = document_repository

    async def post_process_document(
            self,
            document_id: int,
            post_process_document_request: PostProcessDocumentRequest,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> PostProcessDocumentResponse:
        logger.info(
            "Post-process document initiated",
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
            self._authorize_or_raise(
                document=document,
                user=user
            )
            updated_document = await self._apply_and_persist(
                document=document,
                post_process_document_request=post_process_document_request,
                user=user,
                database_session=database_session
            )

            logger.info(
                "Post-process document completed",
                extra={
                    "document_id": document_id,
                    "user_id": user.id
                }
            )

            return PostProcessDocumentResponse.model_validate(updated_document)

        except (
                UpdateDocumentNotFoundException,
                UpdateDocumentUnauthorizedException,
                UpdateDocumentFailedException
        ):
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during post-process document",
                extra={
                    "document_id": document_id
                }
            )
            raise UpdateDocumentServiceException(
                f"Unexpected error during post-process of document {document_id}"
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
            raise UpdateDocumentNotFoundException(f"Document {document_id} not found")

        return document

    @staticmethod
    def _authorize_or_raise(
            document: Document,
            user: AuthenticationResponse
    ) -> None:
        if not any(role in user.roles for role in _ADMIN_ROLES):
            logger.warning(
                "Unauthorized post-process attempt",
                extra={
                    "document_id": document.id,
                    "user_id": user.id,
                    "user_roles": list(user.roles)
                }
            )
            raise UpdateDocumentUnauthorizedException(
                f"User {user.id} is not authorized to post-process document {document.id}"
            )

    async def _apply_and_persist(
            self,
            document: Document,
            post_process_document_request: PostProcessDocumentRequest,
            user: AuthenticationResponse,
            database_session: AsyncSession
    ) -> Document:
        try:
            document.type = post_process_document_request.type
            document.category = post_process_document_request.category
            document.description = post_process_document_request.description
            document.updated_by = user.id
            document.updated_at = datetime.now(timezone.utc)

            updated_document: Document = await self._document_repository.update_document(
                document=document,
                database_session=database_session
            )

            logger.info(
                "Document persisted successfully",
                extra={
                    "document_id": document.id,
                    "user_id": user.id
                }
            )

            return updated_document

        except Exception as e:
            raise UpdateDocumentFailedException(
                f"Failed to persist post-process for document {document.id}"
            ) from e
