import logging
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.services.document.document_query_service.document_query_service_settings import (
    DocumentQueryServiceSettings
)
from app.application.authorization.permissions import Permissions
from app.domain.constants.document.document_type import DocumentType
from app.domain.field_limits import MAX_DOCUMENTS_IN_LIST

from app.application.services.document.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryInvalidRequestException,
    DocumentQueryNotFoundException,
    DocumentQueryServiceException,
)
from app.application.services.document.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.dtos.document.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface
)

logger = logging.getLogger(__name__)


class DocumentQueryService(DocumentQueryServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            authorizer: Authorizer,
            document_query_service_settings: Optional[DocumentQueryServiceSettings] = None
    ) -> None:
        self._document_repository = document_repository
        self._settings = document_query_service_settings or DocumentQueryServiceSettings()

        self._authorizer = authorizer

    async def get_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentResponse:
        logger.info(
            "Fetching a single document was initiated.",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        try:
            if document_id <= 0:
                raise DocumentQueryInvalidRequestException("The document identifier must be a positive number.")
            self._authorizer.require_permissions(
                authenticated_user=authenticated_user,
                required_permissions=frozenset({Permissions.GET_DOCUMENT}),
            )

            document = await self._get_document_or_raise(document_id, database_session)

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
                UnauthorizedException,
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
            page: int,
            size: int,
            name: Optional[str] = None,
            description: Optional[str] = None,
            category: Optional[str] = None,
            document_type: Optional[DocumentType] = None,
            created_from: Optional[datetime] = None,
            created_to: Optional[datetime] = None,
    ) -> DocumentListResponse:
        has_filters = any(
            f is not None
            for f in (name, description, category, document_type, created_from, created_to)
        )

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
            self._authorizer.require_permissions(
                authenticated_user=authenticated_user,
                required_permissions=frozenset({Permissions.LIST_DOCUMENTS}),
            )
            if page < 1:
                raise DocumentQueryInvalidRequestException("The page number must be a positive integer.")
            if size < 1:
                raise DocumentQueryInvalidRequestException("The page size must be a positive integer.")
            if size > self._settings.max_page_size:
                raise DocumentQueryInvalidRequestException("The page size exceeds the maximum allowed value.")
            for _field_value in (name, description, category):
                if _field_value is not None and len(_field_value) > self._settings.max_filter_length:
                    raise DocumentQueryInvalidRequestException("A filter value exceeds the maximum allowed length.")
            if created_from and created_to and created_from > created_to:
                raise DocumentQueryInvalidRequestException("The start of the date range cannot be after the end.")

            documents: list[Document] = await self._document_repository.get_documents(
                database_session=database_session,
                page=page,
                size=size,
                name=name,
                description=description,
                category=category,
                document_type=document_type,
                created_from=created_from,
                created_to=created_to,
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
                UnauthorizedException,
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

    async def get_documents_by_chat(
            self,
            chat_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentListResponse:
        logger.info(
            "Fetching documents by chat was initiated.",
            extra={
                "chat_id": chat_id,
                "user_id": authenticated_user.id
            }
        )

        try:
            if chat_id <= 0:
                raise DocumentQueryInvalidRequestException("The chat identifier must be a positive number.")
            self._authorizer.require_permissions(
                authenticated_user=authenticated_user,
                required_permissions=frozenset({Permissions.LIST_DOCUMENTS_BY_CHAT}),
            )

            documents = await self._document_repository.get_documents_by_chat_id(
                chat_id=chat_id,
                database_session=database_session,
            )

            if len(documents) > MAX_DOCUMENTS_IN_LIST:
                raise DocumentQueryInvalidRequestException(
                    "The number of documents in this chat exceeds the maximum allowed for a single request."
                )

            logger.info(
                "Documents by chat were fetched successfully.",
                extra={
                    "chat_id": chat_id,
                    "count": len(documents),
                    "user_id": authenticated_user.id
                }
            )

            return DocumentListResponse(
                documents=[DocumentResponse.model_validate(d) for d in documents]
            )

        except (
                DocumentQueryNotFoundException,
                UnauthorizedException,
                DocumentQueryInvalidRequestException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while fetching documents by chat.",
                extra={
                    "chat_id": chat_id
                }
            )
            raise DocumentQueryServiceException(
                "An unexpected error occurred while fetching documents by chat."
            ) from e

    async def _get_document_or_raise(
            self,
            document_id: int,
            database_session: AsyncSession,
    ) -> Document:
        document = await self._document_repository.get_document_by_id(
            document_id=document_id,
            database_session=database_session,
        )
        if document is None:
            logger.warning(
                "The document was not found.",
                extra={
                    "document_id": document_id,
                },
            )
            raise DocumentQueryNotFoundException("The document was not found.")
        return document


async def get_document_query_service(
        request: Request,
) -> DocumentQueryServiceInterface:
    try:
        return request.app.state.document_query_service
    except AttributeError:
        logger.error("DocumentQueryService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentQueryService is not registered on the application state.",
        )
