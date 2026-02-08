from typing import Optional

from sqlalchemy.orm import Session
import logging

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.services.document_retrieve_service.document_context_service_configuration import (
    DocumentContextServiceConfiguration
)
from app.application.services.document_retrieve_service.interfaces.document_context_service_interface import (
    DocumentContextServiceInterface
)
from app.domain.dtos.document_retrieve.context_fragments_response import ContextFragmentsResponse
from app.domain.dtos.document_retrieve.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.document_retrieve.question_context_fragments_request import QuestionContextFragmentsRequest
from app.infrastructure.persistence.repositories.exceptions.database_exceptions import DatabaseError
from app.infrastructure.persistence.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class DocumentContextService(DocumentContextServiceInterface):
    def __init__(
            self,
            fragment_repository: FragmentRepositoryInterface,
            embedder_factory: EmbedderFactory,
            document_context_service_configuration: DocumentContextServiceConfiguration
    ):
        self._fragment_repository = fragment_repository
        self._embedder_factory = embedder_factory

        self._document_context_service_configuration = document_context_service_configuration or DocumentContextServiceConfiguration()

        logger.info("DocumentContextService initialized")

    @classmethod
    def create(
            cls,
            fragment_repository: FragmentRepositoryInterface,
            embedder_factory: EmbedderFactory,
            embedder_type: Optional[str] = None
    ) -> "DocumentContextService":
        config_kwargs = {}

        if embedder_type is not None:
            config_kwargs['embedder_type'] = embedder_type

        document_context_service_configuration = DocumentContextServiceConfiguration(
            **config_kwargs
        )

        return cls(
            fragment_repository=fragment_repository,
            embedder_factory=embedder_factory,
            document_context_service_configuration=document_context_service_configuration
        )

    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            db: Session
    ) -> ContextFragmentsResponse:
        try:
            embedder = self._embedder_factory.get_embedder(
                method=self._document_context_service_configuration.embedder_type
            )
            embedded_query = embedder.embed_query(
                text=question_context_fragments_request.question
            )

            fragments = self._fragment_repository.get_most_similar_fragments(
                query_vector=embedded_query,
                db=db,
                k=question_context_fragments_request.max_context_fragments
            )

            logger.info("Relevant fragments retrieved")

            context_fragments = []
            for fragment in fragments:
                context_fragments.append(fragment.content)

            return ContextFragmentsResponse(
                context_fragments=context_fragments
            )

        except Exception as e:
            logger.exception("Error in retrieval process")
            raise DatabaseError("Error al procesar la recuperación de fragmentos") from e

    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            db: Session
    ) -> ContextFragmentsResponse:
        try:
            fragments = self._fragment_repository.get_fragments_by_document_id(
                document_id=document_context_fragments_request.document_id,
                db=db
            )

            logger.info("Fragments retrieved")

            context_fragments = []
            for fragment in fragments:
                context_fragments.append(fragment.content)

            return ContextFragmentsResponse(
                context_fragments=context_fragments
            )

        except Exception as e:
            logger.exception("Error in retrieval process")
            raise DatabaseError("Error al procesar la recuperación de fragmentos") from e
