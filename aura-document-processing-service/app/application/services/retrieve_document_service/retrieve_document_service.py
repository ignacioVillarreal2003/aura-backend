import logging
import time
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.services.retrieve_document_service.retrieve_document_service_settings import (
    RetrieveDocumentServiceSettings
)
from app.application.services.retrieve_document_service.interfaces.retrieve_document_service_interface import (
    RetrieveDocumentServiceInterface
)
from app.application.services.retrieve_document_service.exceptions.retrieve_document_service_exceptions import (
    EmbeddingException,
    FragmentRetrievalException, RetrieveDocumentServiceException
)
from app.domain.dtos.retrieve_document.context_fragment_response import ContextFragmentResponse
from app.domain.dtos.retrieve_document.context_fragments_response import ContextFragmentsResponse
from app.domain.dtos.retrieve_document.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.retrieve_document.question_context_fragments_request import QuestionContextFragmentsRequest
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class RetrieveDocumentService(RetrieveDocumentServiceInterface):
    def __init__(
            self,
            fragment_repository: FragmentRepositoryInterface,
            embedder_factory: EmbedderFactory,
            retrieve_document_service_settings: RetrieveDocumentServiceSettings
    ):
        self._fragment_repository = fragment_repository
        self._embedder_factory = embedder_factory
        self._retrieve_document_service_settings = retrieve_document_service_settings

        self._question_queries = 0
        self._document_queries = 0
        self._failed_queries = 0
        self._embedding_errors = 0
        self._retrieval_errors = 0
        self._total_fragments_returned = 0
        self._total_query_time = 0.0
        self._last_health_check: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
            cls,
            fragment_repository: FragmentRepositoryInterface,
            embedder_factory: EmbedderFactory,
            embedder_type: Optional[str] = None,
            **config_kwargs
    ) -> "RetrieveDocumentService":
        if embedder_type is not None:
            config_kwargs['embedder_type'] = embedder_type

        retrieve_document_service_settings = RetrieveDocumentServiceSettings(
            **config_kwargs
        )

        return cls(
            fragment_repository=fragment_repository,
            embedder_factory=embedder_factory,
            retrieve_document_service_settings=retrieve_document_service_settings
        )

    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            database_session: AsyncSession
    ) -> ContextFragmentsResponse:
        start_time = time.time()

        logger.info(
            "Retrieving context fragments by question",
            extra={
                "question_length": len(question_context_fragments_request.question),
                "max_fragments": question_context_fragments_request.max_context_fragments
            }
        )

        try:
            try:
                embedder = self._embedder_factory.get_embedder(
                    method=self._retrieve_document_service_settings.embedder_type
                )
                embedded_query = embedder.embed_query(
                    text=question_context_fragments_request.question
                )

                logger.debug("Query embedding generated")

            except Exception as e:
                self._embedding_errors += 1
                logger.error(
                    "Failed to generate embedding",
                    extra={
                        "error": str(e)
                    }
                )
                raise EmbeddingException(f"Failed to generate query embedding: {str(e)}") from e

            try:
                fragments = await self._fragment_repository.get_most_similar_fragments(
                    query_vector=embedded_query,
                    database_session=database_session,
                    k=question_context_fragments_request.max_context_fragments
                )

                logger.info(
                    "Similar fragments retrieved",
                    extra={
                        "num_fragments": len(fragments)
                    }
                )

            except Exception as e:
                self._retrieval_errors += 1
                logger.error(
                    "Failed to retrieve fragments",
                    extra={
                        "error": str(e)
                    }
                )
                raise FragmentRetrievalException(f"Failed to retrieve similar fragments: {str(e)}") from e

            self._question_queries += 1
            self._total_fragments_returned += len(fragments)

            elapsed = time.time() - start_time
            self._total_query_time += elapsed

            logger.info(
                "Question-based retrieval completed",
                extra={
                    "num_fragments": len(fragments),
                    "elapsed_seconds": round(elapsed, 2)
                }
            )

            context_fragments = [
                ContextFragmentResponse.model_validate(f) for f in fragments
            ]

            return ContextFragmentsResponse(
                context_fragments=context_fragments
            )

        except (
                EmbeddingException,
                FragmentRetrievalException
        ):
            self._failed_queries += 1
            raise

        except Exception as e:
            self._failed_queries += 1
            logger.exception("Unexpected error in question-based retrieval")
            raise RetrieveDocumentServiceException(f"Failed to retrieve context fragments: {str(e)}") from e

    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            database_session: AsyncSession
    ) -> ContextFragmentsResponse:
        start_time = time.time()

        logger.info(
            "Retrieving context fragments by document",
            extra={
                "document_id": document_context_fragments_request.document_id
            }
        )

        try:
            try:
                fragments = await self._fragment_repository.get_fragments_by_document_id(
                    document_id=document_context_fragments_request.document_id,
                    database_session=database_session
                )

                logger.info(
                    "Document fragments retrieved",
                    extra={
                        "document_id": document_context_fragments_request.document_id,
                        "num_fragments": len(fragments)
                    }
                )

            except Exception as e:
                self._retrieval_errors += 1
                logger.error(
                    "Failed to retrieve document fragments",
                    extra={
                        "document_id": document_context_fragments_request.document_id,
                        "error": str(e)
                    }
                )
                raise FragmentRetrievalException(f"Failed to retrieve document fragments: {str(e)}") from e

            self._document_queries += 1
            self._total_fragments_returned += len(fragments)

            elapsed = time.time() - start_time
            self._total_query_time += elapsed

            logger.info(
                "Document-based retrieval completed",
                extra={
                    "document_id": document_context_fragments_request.document_id,
                    "num_fragments": len(fragments),
                    "elapsed_seconds": round(elapsed, 2)
                }
            )

            context_fragments = [
                ContextFragmentResponse.model_validate(f) for f in fragments
            ]

            return ContextFragmentsResponse(
                context_fragments=context_fragments
            )

        except FragmentRetrievalException:
            self._failed_queries += 1
            raise

        except Exception as e:
            self._failed_queries += 1
            logger.exception("Unexpected error in document-based retrieval")
            raise RetrieveDocumentServiceException(f"Failed to retrieve document fragments: {str(e)}") from e

    def get_metrics(
            self
    ) -> Dict[str, int]:
        return {
            "question_queries": self._question_queries,
            "document_queries": self._document_queries,
            "failed_queries": self._failed_queries,
            "embedding_errors": self._embedding_errors,
            "retrieval_errors": self._retrieval_errors,
            "total_fragments_returned": self._total_fragments_returned,
        }
