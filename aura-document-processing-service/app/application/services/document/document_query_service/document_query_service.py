import logging
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.document.document_query_service.document_query_service_authorizer import (
    DocumentQueryServiceAuthorizer
)
from app.application.services.document.document_query_service.document_query_service_settings import (
    DocumentQueryServiceSettings
)
from app.application.services.document.document_query_service.document_query_service_validator import (
    DocumentQueryServiceValidator
)
from app.domain.constants.user.user_roles import (
    ADMIN_ROLES,
    ALL_ROLES
)
from app.domain.constants.document.document_type import DocumentType

from app.application.services.document.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryInvalidRequestException,
    DocumentQueryNotFoundException,
    DocumentQueryServiceException,
    DocumentQueryUnauthorizedException
)
from app.application.services.document.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.dtos.document.document_query_controller.document_list_response import DocumentListResponse
from app.domain.dtos.document.document_query_controller.document_response import DocumentResponse
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.models.document import Document
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)

logger = logging.getLogger(__name__)


class DocumentQueryService(DocumentQueryServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            document_query_service_settings: Optional[DocumentQueryServiceSettings] = None
    ) -> None:
        self._document_repository = document_repository
        self._settings = document_query_service_settings or DocumentQueryServiceSettings()

        self._validator = DocumentQueryServiceValidator(
            document_query_service_settings=self._settings
        )
        self._authorizer = DocumentQueryServiceAuthorizer()

    async def get_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> DocumentResponse:
        logger.info(
            "Fetching a single document was initiated.",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        try:
            self._validator.validate_document_id(document_id)
            self._authorizer.require_permissions(authenticated_user)
            self._authorizer.require_roles(
                authenticated_user=authenticated_user,
                allowed_roles=ALL_ROLES
            )

            document = await self._get_document_or_raise(document_id, database_session)

            if not authenticated_user.has_any_role(ADMIN_ROLES):
                self._authorizer.require_ownership(document, authenticated_user)

            logger.info(
                "The document was fetched successfully.",
                extra={
                    "document_id": document_id,
                    "user_id": authenticated_user.id
                }
            )
            return DocumentResponse.model_validate(document)

        except (
                DocumentQueryNotFoundException,
                DocumentQueryUnauthorizedException,
                DocumentQueryInvalidRequestException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while fetching the document.",
                extra={
                    "document_id": document_id
                }
            )
            raise DocumentQueryServiceException("An unexpected error occurred while fetching the document.") from e

    async def get_documents(
            self,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
            page: Optional[int] = None,
            size: Optional[int] = None,
            name: Optional[str] = None,
            description: Optional[str] = None,
            category: Optional[str] = None,
            type: Optional[DocumentType] = None,
            created_from: Optional[datetime] = None,
            created_to: Optional[datetime] = None
    ) -> DocumentListResponse:
        has_filters = any(f is not None for f in (name, description, category, type, created_from, created_to))

        logger.info(
            "Fetching the document list was initiated.",
            extra={
                "page": page,
                "size": size,
                "has_filters": has_filters,
                "user_id": authenticated_user.id
            }
        )

        try:
            self._authorizer.require_permissions(authenticated_user)
            self._authorizer.require_roles(
                authenticated_user=authenticated_user,
                allowed_roles=ADMIN_ROLES
            )
            self._validator.validate_pagination(page, size)
            self._validator.validate_filters(
                name=name,
                description=description,
                category=category,
                created_from=created_from,
                created_to=created_to
            )

            if has_filters:
                documents: list[Document] = await self._document_repository.get_documents(
                    database_session=database_session,
                    page=page,
                    size=size,
                    name=name,
                    description=description,
                    category=category,
                    type=type,
                    created_from=created_from,
                    created_to=created_to
                )
            else:
                documents = await self._document_repository.get_documents(
                    page=page,
                    size=size,
                    database_session=database_session
                )

            logger.info(
                "The document list was fetched successfully.",
                extra={
                    "page": page,
                    "size": size,
                    "count": len(documents),
                    "user_id": authenticated_user.id
                }
            )

            return DocumentListResponse(
                documents=[DocumentResponse.model_validate(d) for d in documents]
            )


        except (
                DocumentQueryNotFoundException,
                DocumentQueryUnauthorizedException,
                DocumentQueryInvalidRequestException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while fetching documents.",
                extra={
                    "page": page,
                    "size": size
                }
            )
            raise DocumentQueryServiceException("An unexpected error occurred while fetching documents.") from e

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
            raise DocumentQueryNotFoundException("The document was not found.")
        return document


async def get_document_query_service(
        request: Request
) -> DocumentQueryServiceInterface:
    try:
        return request.app.state.document_query_service
    except AttributeError:
        logger.error("DocumentQueryService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentQueryService is not registered on the application state."
        )
