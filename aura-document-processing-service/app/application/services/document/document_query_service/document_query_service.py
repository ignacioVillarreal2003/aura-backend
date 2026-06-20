import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.services.document.document_query_service.document_query_service_settings import (
    DocumentQueryServiceSettings,
)
from app.domain.constants.document.document_type import DocumentType

from app.application.services.document.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryInvalidRequestException,
    DocumentQueryNotFoundException,
    DocumentQueryServiceException,
)
from app.application.services.document.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface,
)
from app.domain.dtos.document.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.dtos.document.document_query.document_status_response import DocumentStatusResponse
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.chat_membership.interfaces.chat_membership_provider_interface import (
    ChatMembershipProviderInterface,
)
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.http.document_collection_catalog.interfaces.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)

logger = logging.getLogger(__name__)


class DocumentQueryService(DocumentQueryServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            document_collection_catalog_client: DocumentCollectionCatalogClientInterface,
            chat_membership_provider: ChatMembershipProviderInterface,
            document_query_service_settings: Optional[DocumentQueryServiceSettings] = None
    ) -> None:
        self._document_repository = document_repository
        self._document_collection_catalog_client = document_collection_catalog_client
        self._chat_membership_provider = chat_membership_provider
        self._settings = document_query_service_settings or DocumentQueryServiceSettings()

    async def get_document_manage(
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

    async def get_document_status_manage(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentStatusResponse:
        logger.info(
            "Fetching the processing status of a document was initiated.",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        try:
            if document_id <= 0:
                raise DocumentQueryInvalidRequestException("The document identifier must be a positive number.")

            document = await self._get_document_or_raise(document_id, database_session)

            logger.info(
                "The document status was fetched successfully.",
                extra={
                    "document_id": document_id,
                    "user_id": authenticated_user.id
                }
            )
            return DocumentStatusResponse.model_validate(document)

        except (
                DocumentQueryNotFoundException,
                UnauthorizedException,
                DocumentQueryInvalidRequestException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while fetching the document status.",
                extra={
                    "document_id": document_id
                }
            )
            raise DocumentQueryServiceException(
                "An unexpected error occurred while fetching the document status."
            ) from e

    async def get_document_status(
            self,
            document_id: int,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentStatusResponse:
        logger.info(
            "Fetching the processing status of a document was initiated.",
            extra={
                "document_id": document_id,
                "user_id": authenticated_user.id
            }
        )

        try:
            if document_id <= 0:
                raise DocumentQueryInvalidRequestException("The document identifier must be a positive number.")

            document = await self._get_document_or_raise(document_id, database_session)

            await self._require_document_access(document, authenticated_user)

            logger.info(
                "The document status was fetched successfully.",
                extra={
                    "document_id": document_id,
                    "user_id": authenticated_user.id
                }
            )
            return DocumentStatusResponse.model_validate(document)

        except (
                DocumentQueryNotFoundException,
                UnauthorizedException,
                DocumentQueryInvalidRequestException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while fetching the document status.",
                extra={
                    "document_id": document_id
                }
            )
            raise DocumentQueryServiceException(
                "An unexpected error occurred while fetching the document status."
            ) from e

    async def get_documents_manage(
            self,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
            page: Optional[int] = None,
            size: Optional[int] = None,
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
        paginate = page is not None or size is not None

        logger.info(
            "Fetching the document list was initiated.",
            extra={
                "page": page,
                "size": size,
                "paginated": paginate,
                "has_filters": has_filters,
                "user_id": authenticated_user.id
            }
        )

        try:
            effective_page: Optional[int] = None
            effective_size: Optional[int] = None
            if paginate:
                effective_page = page if page is not None else self._settings.default_page
                effective_size = size if size is not None else self._settings.default_page_size
                if effective_page < 1:
                    raise DocumentQueryInvalidRequestException("The page number must be a positive integer.")
                if effective_size < 1:
                    raise DocumentQueryInvalidRequestException("The page size must be a positive integer.")
                if effective_size > self._settings.max_page_size:
                    raise DocumentQueryInvalidRequestException("The page size exceeds the maximum allowed value.")

            for _field_value in (name, description, category):
                if _field_value is not None and len(_field_value) > self._settings.max_filter_length:
                    raise DocumentQueryInvalidRequestException("A filter value exceeds the maximum allowed length.")
            if created_from and created_to and created_from > created_to:
                raise DocumentQueryInvalidRequestException("The start of the date range cannot be after the end.")

            documents: list[Document] = await self._document_repository.get_documents(
                database_session=database_session,
                page=effective_page,
                size=effective_size,
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
                    "page": effective_page,
                    "size": effective_size,
                    "paginated": paginate,
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
            page: Optional[int] = None,
            size: Optional[int] = None,
    ) -> DocumentListResponse:
        paginate = page is not None or size is not None

        logger.info(
            "Fetching documents by chat was initiated.",
            extra={
                "chat_id": chat_id,
                "page": page,
                "size": size,
                "paginated": paginate,
                "user_id": authenticated_user.id
            }
        )

        try:
            if chat_id <= 0:
                raise DocumentQueryInvalidRequestException("The chat identifier must be a positive number.")

            effective_page: Optional[int] = None
            effective_size: Optional[int] = None
            if paginate:
                effective_page = page if page is not None else self._settings.default_page
                effective_size = size if size is not None else self._settings.default_page_size
                if effective_page < 1:
                    raise DocumentQueryInvalidRequestException("The page number must be a positive integer.")
                if effective_size < 1:
                    raise DocumentQueryInvalidRequestException("The page size must be a positive integer.")
                if effective_size > self._settings.max_page_size:
                    raise DocumentQueryInvalidRequestException("The page size exceeds the maximum allowed value.")

            membership = await self._chat_membership_provider.get_membership(
                chat_id=chat_id,
                user_id=int(authenticated_user.id),
                authorization_header=get_request_token(),
            )
            if not membership.is_member:
                logger.warning(
                    "Unauthorized list documents by chat attempt.",
                    extra={
                        "chat_id": chat_id,
                        "user_id": authenticated_user.id,
                    },
                )
                raise UnauthorizedException(
                    "You are not authorized to list documents for this chat."
                )

            documents = await self._document_repository.get_documents_by_chat_id(
                chat_id=chat_id,
                database_session=database_session,
                page=effective_page,
                size=effective_size,
            )

            logger.info(
                "Documents by chat were fetched successfully.",
                extra={
                    "chat_id": chat_id,
                    "page": effective_page,
                    "size": effective_size,
                    "paginated": paginate,
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

    async def _require_document_access(
            self,
            document: Document,
            authenticated_user: AuthenticatedUser,
    ) -> None:
        authorization_header = get_request_token()

        accessible_ids = await self._document_collection_catalog_client.fetch_all_accessible_document_ids(
            user_id=int(authenticated_user.id),
            authorization_header=authorization_header,
        )
        if int(document.id) in accessible_ids:
            return

        if document.chat_id is not None:
            membership = await self._chat_membership_provider.get_membership(
                chat_id=int(document.chat_id),
                user_id=int(authenticated_user.id),
                authorization_header=authorization_header,
            )
            if membership.is_member:
                return

        logger.warning(
            "Unauthorized document access attempt.",
            extra={
                "document_id": document.id,
                "user_id": authenticated_user.id,
            },
        )
        raise UnauthorizedException("You are not authorized to access this document.")

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
