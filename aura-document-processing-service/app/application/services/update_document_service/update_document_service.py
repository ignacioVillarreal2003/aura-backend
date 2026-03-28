import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, Request, status

from app.application.services.update_document_service.exceptions.update_document_service_exception import (
    UpdateDocumentFailedException,
    UpdateDocumentNotFoundException,
    UpdateDocumentServiceException,
    UpdateDocumentUnauthorizedException
)
from app.application.services.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface
)
from app.domain.dtos.update_document_controller.post_process_document_request import PostProcessDocumentRequest
from app.domain.dtos.update_document_controller.post_process_document_response import PostProcessDocumentResponse
from app.domain.models.document import Document
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import AuthenticationResponse
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)

logger = logging.getLogger(__name__)


class UpdateDocumentService(UpdateDocumentServiceInterface):
    _ROLE_ADMIN = "admin"
    _ROLE_SUPERADMIN = "superadmin"

    _ADMIN_ROLES = {_ROLE_ADMIN, _ROLE_SUPERADMIN}

    _PERMISSION_DOCUMENT_UPDATE = "DOCUMENT_UPDATE"
    _REQUIRED_PERMISSIONS = {_PERMISSION_DOCUMENT_UPDATE}

    _KNOWN_EXCEPTIONS = (
        UpdateDocumentNotFoundException,
        UpdateDocumentUnauthorizedException,
        UpdateDocumentFailedException,
    )

    def __init__(self, document_repository: DocumentRepositoryInterface) -> None:
        self._document_repository = document_repository

    async def post_process_document(
            self,
            document_id: int,
            post_process_document_request: PostProcessDocumentRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> PostProcessDocumentResponse:
        logger.info(
            "Post-process document initiated",
            extra={"document_id": document_id, "user_id": authenticated_user.id}
        )

        try:
            self._require_permissions(authenticated_user)
            self._require_roles(authenticated_user, context=f"post_process_document({document_id})")

            document = await self._get_document_or_raise(document_id, database_session)
            updated_document = await self._apply_and_persist(
                document=document,
                request=post_process_document_request,
                authenticated_user=authenticated_user,
                database_session=database_session
            )

            logger.info(
                "Post-process document completed",
                extra={"document_id": document_id, "user_id": authenticated_user.id}
            )
            return PostProcessDocumentResponse.model_validate(updated_document)

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during post-process document",
                extra={"document_id": document_id}
            )
            raise UpdateDocumentServiceException(
                f"Unexpected error during post-process of document {document_id}"
            ) from e

    def _require_permissions(self, authenticated_user: AuthenticationResponse) -> None:
        user_permissions = set(authenticated_user.permissions)
        missing = self._REQUIRED_PERMISSIONS - user_permissions

        if missing:
            logger.warning(
                "Insufficient permissions for update operation",
                extra={
                    "user_id": authenticated_user.id,
                    "missing_permissions": sorted(missing),
                    "user_permissions": sorted(user_permissions),
                },
            )
            raise UpdateDocumentUnauthorizedException(
                f"User {authenticated_user.id} is missing required permissions: {sorted(missing)}"
            )

    def _require_roles(self, authenticated_user: AuthenticationResponse, context: str) -> None:
        if not bool(set(authenticated_user.roles) & self._ADMIN_ROLES):
            logger.warning(
                "Insufficient role for update operation",
                extra={
                    "user_id": authenticated_user.id,
                    "user_roles": sorted(authenticated_user.roles),
                    "allowed_roles": sorted(self._ADMIN_ROLES),
                    "context": context,
                },
            )
            raise UpdateDocumentUnauthorizedException(
                f"User {authenticated_user.id} does not have the required role for {context}. "
                f"Allowed roles: {sorted(self._ADMIN_ROLES)}"
            )

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
            raise UpdateDocumentNotFoundException(f"Document {document_id} not found")
        return document

    async def _apply_and_persist(
            self,
            document: Document,
            request: PostProcessDocumentRequest,
            authenticated_user: AuthenticationResponse,
            database_session: AsyncSession
    ) -> Document:
        try:
            document.type = request.type
            document.category = request.category
            document.description = request.description
            document.updated_by = authenticated_user.id
            document.updated_at = datetime.now(timezone.utc)

            updated_document: Document = await self._document_repository.update_document(
                document=document,
                database_session=database_session
            )

            logger.debug(
                "Document persisted successfully",
                extra={"document_id": document.id, "user_id": authenticated_user.id}
            )
            return updated_document

        except Exception as e:
            raise UpdateDocumentFailedException(
                f"Failed to persist post-process for document {document.id}"
            ) from e

async def get_update_document_service(request: Request) -> UpdateDocumentServiceInterface:
    try:
        return request.app.state.update_document_service
    except AttributeError:
        logger.error("UpdateDocumentService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="UpdateDocumentService not configured",
        )
