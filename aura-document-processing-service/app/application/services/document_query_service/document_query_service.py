import logging
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.document_query_service.document_query_service_settings import (
    DocumentQueryServiceSettings
)
from app.application.services.document_query_service.exceptions.document_query_service_exception import (
    DocumentNotFoundError,
    DocumentQueryException
)
from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.dtos.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document_query.document_response import DocumentResponse
from app.domain.models.document import Document
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)

logger = logging.getLogger(__name__)


class DocumentQueryService(DocumentQueryServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            document_query_service_settings: DocumentQueryServiceSettings
    ):
        self._document_repository = document_repository
        self._document_query_service_settings = document_query_service_settings

        self._single_queries = 0
        self._list_queries = 0
        self._failed_queries = 0
        self._not_found_errors = 0
        self._total_documents_returned = 0
        self._last_health_check: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
            cls,
            document_repository: DocumentRepositoryInterface,
            **config_kwargs
    ) -> "DocumentQueryService":
        document_query_service_settings = DocumentQueryServiceSettings(
            **config_kwargs
        )

        return cls(
            document_repository=document_repository,
            document_query_service_settings=document_query_service_settings
        )

    async def get_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> DocumentResponse:
        logger.info(
            "Retrieving document by ID",
            extra={
                "document_id": document_id
            }
        )

        try:
            document: Optional[Document] = await self._document_repository.get_document_by_id(
                document_id=document_id,
                database_session=database_session
            )

            if document is None:
                self._not_found_errors += 1
                logger.warning(
                    "Document not found",
                    extra={
                        "document_id": document_id
                    }
                )
                raise DocumentNotFoundError(f"Document with ID {document_id} not found")

            self._single_queries += 1
            self._total_documents_returned += 1

            logger.info(
                "Document retrieved successfully",
                extra={
                    "document_id": document_id
                }
            )

            return DocumentResponse(
                id=document.id,
                name=document.name,
                type=document.type,
                status=document.status,
                path=document.path
            )

        except DocumentNotFoundError:
            self._failed_queries += 1
            raise

        except Exception as e:
            self._failed_queries += 1
            logger.exception(
                "Error retrieving document",
                extra={
                    "document_id": document_id
                }
            )
            raise DocumentQueryException(f"Failed to retrieve document: {str(e)}") from e

    async def get_documents(
            self,
            page: Optional[int],
            size: Optional[int],
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> DocumentListResponse:
        page = page if page is not None else 1
        size = size if size is not None else self._document_query_service_settings.default_page_size

        if size > self._document_query_service_settings.max_page_size:
            logger.warning(
                f"Page size {size} exceeds max {self._document_query_service_settings.max_page_size}, using max")
            size = self._document_query_service_settings.max_page_size

        logger.info(
            "Retrieving documents list",
            extra={
                "page": page,
                "size": size
            }
        )

        try:
            documents: List[Document] = await self._document_repository.get_documents(
                page=page,
                size=size,
                database_session=database_session
            )

            document_list: List[DocumentResponse] = [
                DocumentResponse(
                    id=d.id,
                    name=d.name,
                    type=d.type,
                    status=d.status,
                    path=d.path
                ) for d in documents
            ]

            self._list_queries += 1
            self._total_documents_returned += len(document_list)

            logger.info(
                "Documents retrieved successfully",
                extra={
                    "page": page,
                    "size": size,
                    "count": len(document_list)
                }
            )

            return DocumentListResponse(
                documents=document_list
            )

        except Exception as e:
            self._failed_queries += 1
            logger.exception("Error retrieving documents list")
            raise DocumentQueryException(f"Failed to retrieve documents: {str(e)}") from e

    def get_metrics(
            self
    ) -> Dict[str, int]:
        return {
            "single_queries": self._single_queries,
            "list_queries": self._list_queries,
            "failed_queries": self._failed_queries,
            "not_found_errors": self._not_found_errors,
            "total_documents_returned": self._total_documents_returned,
        }
