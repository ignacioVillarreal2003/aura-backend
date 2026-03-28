import logging
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.constants.document.document_type import DocumentType

from app.application.services.document_query_service.document_query_service_request_validator import (
    DocumentQueryServiceRequestValidator
)
from app.application.services.document_query_service.document_query_service_settings import (
    DocumentQueryServiceSettings
)
from app.application.services.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryInvalidRequestException,
    DocumentQueryNotFoundException,
    DocumentQueryServiceException,
    DocumentQueryUnauthorizedException
)
from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.dtos.document.document_query_controller.document_response import DocumentListResponse, DocumentResponse
from app.domain.models.document import Document
from app.infrastructure.http.authentication_provider.dtos.authenticated_user_response import AuthenticationResponse
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)

logger = logging.getLogger(__name__)


class DocumentQueryService(DocumentQueryServiceInterface):
    _ROLE_USER = "user"
    _ROLE_ADMIN = "admin"
    _ROLE_SUPERADMIN = "superadmin"

    _ADMIN_ROLES = {_ROLE_ADMIN, _ROLE_SUPERADMIN}
    _ALL_ALLOWED_ROLES = {_ROLE_USER, _ROLE_ADMIN, _ROLE_SUPERADMIN}

    _PERMISSION_DOCUMENT_GET = "DOCUMENT_GET"
    _REQUIRED_PERMISSIONS = {_PERMISSION_DOCUMENT_GET}

    _KNOWN_EXCEPTIONS = (
        DocumentQueryNotFoundException,
        DocumentQueryUnauthorizedException,
        DocumentQueryInvalidRequestException,
    )

    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            document_query_service_settings: Optional[DocumentQueryServiceSettings] = None
    ) -> None:
        self._document_repository = document_repository
        self._settings = document_query_service_settings or DocumentQueryServiceSettings()

        self._validator = DocumentQueryServiceRequestValidator(
            document_query_service_settings=self._settings
        )

    async def get_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse
    ) -> DocumentResponse:
        logger.info(
            "Get document initiated",
            extra={"document_id": document_id, "user_id": authenticated_user.id}
        )

        try:
            self._require_permissions(authenticated_user)
            self._require_roles(authenticated_user, self._ALL_ALLOWED_ROLES, context=f"get_document({document_id})")

            document = await self._get_document_or_raise(document_id, database_session)

            if not self._has_any_role(authenticated_user, self._ADMIN_ROLES):
                self._require_ownership(document, authenticated_user)

            logger.info(
                "Get document completed",
                extra={"document_id": document_id, "user_id": authenticated_user.id}
            )
            return DocumentResponse.model_validate(document)

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception("Unexpected error during get document", extra={"document_id": document_id})
            raise DocumentQueryServiceException(
                f"Unexpected error retrieving document {document_id}"
            ) from e

    async def get_documents(
            self,
            database_session: AsyncSession,
            authenticated_user: AuthenticationResponse,
            page: Optional[int] = None,
            size: Optional[int] = None,
            name: Optional[str] = None,
            description: Optional[str] = None,
            category: Optional[str] = None,
            type: Optional[DocumentType] = None,
            created_from: Optional[datetime] = None,
            created_to: Optional[datetime] = None,
    ) -> DocumentListResponse:
        has_filters = any(f is not None for f in (name, description, category, type, created_from, created_to))

        logger.info(
            "Get documents initiated",
            extra={"page": page, "size": size, "has_filters": has_filters, "user_id": authenticated_user.id}
        )

        try:
            self._require_permissions(authenticated_user)
            self._require_roles(authenticated_user, self._ADMIN_ROLES, context="get_documents")
            self._validator.validate_pagination(page, size)

            if has_filters:
                documents: list[Document] = await self._document_repository.search_documents(
                    database_session=database_session,
                    page=page,
                    size=size,
                    name=name,
                    description=description,
                    category=category,
                    type=type,
                    created_from=created_from,
                    created_to=created_to,
                )
            else:
                documents = await self._document_repository.get_documents(
                    page=page,
                    size=size,
                    database_session=database_session
                )

            logger.info(
                "Get documents completed",
                extra={"page": page, "size": size, "count": len(documents), "user_id": authenticated_user.id}
            )

            return DocumentListResponse(
                documents=[DocumentResponse.model_validate(d) for d in documents]
            )

        except self._KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception("Unexpected error during get documents", extra={"page": page, "size": size})
            raise DocumentQueryServiceException("Unexpected error retrieving documents") from e

    def _require_permissions(self, authenticated_user: AuthenticationResponse) -> None:
        user_permissions = set(authenticated_user.permissions)
        missing = self._REQUIRED_PERMISSIONS - user_permissions

        if missing:
            logger.warning(
                "Insufficient permissions for query operation",
                extra={
                    "user_id": authenticated_user.id,
                    "missing_permissions": sorted(missing),
                    "user_permissions": sorted(user_permissions)
                }
            )
            raise DocumentQueryUnauthorizedException(
                f"User {authenticated_user.id} is missing required permissions: {sorted(missing)}"
            )

    @staticmethod
    def _require_roles(
            authenticated_user: AuthenticationResponse,
            allowed_roles: set[str],
            context: str
    ) -> None:
        if not DocumentQueryService._has_any_role(authenticated_user, allowed_roles):
            logger.warning(
                "Insufficient role for query operation",
                extra={
                    "user_id": authenticated_user.id,
                    "user_roles": sorted(authenticated_user.roles),
                    "allowed_roles": sorted(allowed_roles),
                    "context": context
                }
            )
            raise DocumentQueryUnauthorizedException(
                f"User {authenticated_user.id} does not have the required role for {context}. "
                f"Allowed roles: {sorted(allowed_roles)}"
            )

    @staticmethod
    def _require_ownership(document: Document, authenticated_user: AuthenticationResponse) -> None:
        if document.created_by != authenticated_user.id:
            logger.warning(
                "Unauthorized document access attempt",
                extra={
                    "document_id": document.id,
                    "owner_id": document.created_by,
                    "user_id": authenticated_user.id
                }
            )
            raise DocumentQueryUnauthorizedException(
                f"User {authenticated_user.id} is not authorized to access document {document.id}"
            )

    @staticmethod
    def _has_any_role(authenticated_user: AuthenticationResponse, roles: set[str]) -> bool:
        return bool(set(authenticated_user.roles) & roles)

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
            raise DocumentQueryNotFoundException(f"Document {document_id} not found")
        return document


async def get_document_query_service(request: Request) -> DocumentQueryServiceInterface:
    try:
        return request.app.state.document_query_service
    except AttributeError:
        logger.error("DocumentQueryService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentQueryService is not available",
        )
