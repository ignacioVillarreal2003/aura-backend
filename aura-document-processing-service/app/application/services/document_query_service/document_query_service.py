import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.services.document_query_service.document_query_service_request_validator import (
    DocumentQueryServiceRequestValidator
)
from app.application.services.document_query_service.document_query_service_settings import (
    DocumentQueryServiceSettings
)
from app.application.services.document_query_service.exceptions.document_query_service_exception import (
    DocumentQueryNotFoundException,
    DocumentQueryUnauthorizedException,
    DocumentQueryServiceException,
    DocumentQueryInvalidRequestException,
    DocumentQueryEmbeddingException,
    DocumentQueryFragmentRetrievalException
)
from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.domain.dtos.document_query_controller.context_fragment_response import ContextFragmentListResponse
from app.domain.dtos.document_query_controller.document_response import (
    DocumentResponse,
    DocumentListResponse
)
from app.domain.dtos.document_query_controller.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.document_query_controller.question_context_fragments_request import QuestionContextFragmentsRequest
from app.domain.models.document import Document
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class DocumentQueryService(DocumentQueryServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            embedder_factory: EmbedderFactory,
            document_query_service_settings: Optional[DocumentQueryServiceSettings] = None
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._embedder_factory = embedder_factory
        self._document_query_service_settings = document_query_service_settings or DocumentQueryServiceSettings()

        self._document_query_service_request_validator = DocumentQueryServiceRequestValidator(
            document_query_service_settings=self._document_query_service_settings
        )

    async def get_document(
            self,
            document_id: int,
            database_session: AsyncSession,
            user: AuthenticationResponse
    ) -> DocumentResponse:
        logger.info(
            "Get document initiated",
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

            logger.info(
                "Get document completed",
                extra={
                    "document_id": document_id,
                    "user_id": user.id
                }
            )

            return DocumentResponse.model_validate(document)

        except (
                DocumentQueryNotFoundException,
                DocumentQueryUnauthorizedException
        ):
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during get document",
                extra={
                    "document_id": document_id
                }
            )
            raise DocumentQueryServiceException(f"Unexpected error retrieving document {document_id}") from e

    async def get_documents(
            self,
            database_session: AsyncSession,
            user: AuthenticationResponse,
            page: Optional[int] = None,
            size: Optional[int] = None
    ) -> DocumentListResponse:
        logger.info(
            "Get documents initiated",
            extra={
                "page": page,
                "size": size,
                "user_id": user.id
            }
        )

        try:
            documents: List[Document] = await self._document_repository.get_documents(
                page=page,
                size=size,
                database_session=database_session
            )

            logger.info(
                "Get documents completed",
                extra={
                    "page": page,
                    "size": size,
                    "count": len(documents),
                    "user_id": user.id
                }
            )

            return DocumentListResponse(
                documents=[DocumentResponse.model_validate(d) for d in documents]
            )

        except Exception as e:
            logger.exception(
                "Unexpected error during get documents",
                extra={
                    "page": page,
                    "size": size
                }
            )
            raise DocumentQueryServiceException("Unexpected error retrieving documents") from e

    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            database_session: AsyncSession
    ) -> ContextFragmentListResponse:
        question = question_context_fragments_request.question
        max_fragments = question_context_fragments_request.max_context_fragments

        logger.info(
            "Retrieve context fragments by question initiated",
            extra={
                "question_length": len(question),
                "max_fragments": max_fragments
            }
        )

        try:
            self._document_query_service_request_validator.validate_question_context_fragments_request(
                question_context_fragments_request=question_context_fragments_request
            )

            embedded_query = await self._get_embedding(question)
            fragments = await self._retrieve_similar_fragments(
                database_session=database_session,
                query_vector=embedded_query,
                k=max_fragments
            )

            logger.info(
                "Retrieve context fragments by question completed",
                extra={
                    "question_length": len(question),
                    "fragment_count": len(fragments)
                }
            )

            return ContextFragmentListResponse(context_fragments=fragments)

        except (
                DocumentQueryInvalidRequestException,
                DocumentQueryEmbeddingException,
                DocumentQueryFragmentRetrievalException
        ):
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during retrieve context fragments by question",
                extra={
                    "question_length": len(question)
                }
            )
            raise DocumentQueryServiceException("Unexpected error retrieving context fragments by question") from e

    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            database_session: AsyncSession
    ) -> ContextFragmentListResponse:
        document_id = document_context_fragments_request.document_id

        logger.info(
            "Retrieve context fragments by document initiated",
            extra={
                "document_id": document_id
            }
        )

        try:
            self._document_query_service_request_validator.validate_document_context_fragments_request(
                document_context_fragments_request=document_context_fragments_request
            )

            fragments = await self._retrieve_document_fragments(
                database_session=database_session,
                document_id=document_id
            )

            logger.info(
                "Retrieve context fragments by document completed",
                extra={
                    "document_id": document_id,
                    "fragment_count": len(fragments)
                }
            )

            return ContextFragmentListResponse(context_fragments=fragments)

        except (
                DocumentQueryInvalidRequestException,
                DocumentQueryFragmentRetrievalException
        ):
            raise

        except Exception as e:
            logger.exception(
                "Unexpected error during retrieve context fragments by document",
                extra={
                    "document_id": document_id
                }
            )
            raise DocumentQueryServiceException(
                f"Unexpected error retrieving context fragments for document {document_id}"
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
            raise DocumentQueryNotFoundException(f"Document {document_id} not found")

        return document

    @staticmethod
    def _authorize_or_raise(
            document: Document,
            user: AuthenticationResponse
    ) -> None:
        if document.created_by != user.id:
            logger.warning(
                "Unauthorized document access attempt",
                extra={
                    "document_id": document.id,
                    "owner_id": document.created_by,
                    "user_id": user.id
                }
            )
            raise DocumentQueryUnauthorizedException(
                f"User {user.id} is not authorized to access document {document.id}"
            )

    async def _get_embedding(
            self,
            question: str
    ) -> list[float]:
        try:
            embedder = self._embedder_factory.get_embedder(
                embedder_type=self._document_query_service_settings.embedder_type
            )
            embedded_query: list[float] = embedder.embed_query(text=question)

            logger.debug("Query embedding generated")
            return embedded_query

        except Exception as e:
            raise DocumentQueryEmbeddingException(f"Failed to generate query embedding: {e}") from e

    async def _retrieve_similar_fragments(
            self,
            database_session: AsyncSession,
            query_vector: list[float],
            k: int
    ) -> list:
        try:
            fragments = await self._fragment_repository.get_most_similar_fragments(
                query_vector=query_vector,
                database_session=database_session,
                k=k
            )
            logger.debug(
                "Similar fragments retrieved",
                extra={
                    "fragment_count": len(fragments)
                }
            )
            return fragments

        except Exception as e:
            raise DocumentQueryFragmentRetrievalException(f"Failed to retrieve similar fragments: {e}") from e

    async def _retrieve_document_fragments(
            self,
            database_session: AsyncSession,
            document_id: int
    ) -> list:
        try:
            fragments = await self._fragment_repository.get_fragments_by_document_id(
                document_id=document_id,
                database_session=database_session
            )
            logger.debug(
                "Document fragments retrieved",
                extra={
                    "document_id": document_id,
                    "fragment_count": len(fragments)
                }
            )
            return fragments

        except Exception as e:
            raise DocumentQueryFragmentRetrievalException(
                f"Failed to retrieve fragments for document {document_id}: {e}"
            ) from e
