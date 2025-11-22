from sqlalchemy.orm import Session
import logging

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.services.interfaces.retrival_service_interface import RetrivalServiceInterface
from app.configuration.environment_variables import environment_variables
from app.domain.dtos.question_request import QuestionRequest
from app.domain.dtos.question_response import QuestionResponse
from app.application.exceptions.api_exceptions import DatabaseError
from app.infrastructure.messaging.interfaces.question_publisher_interface import QuestionPublisherInterface
from app.infrastructure.persistence.repositories.interfaces.fragment_repository_interface import \
    FragmentRepositoryInterface

logger = logging.getLogger(__name__)


class RetrievalService(RetrivalServiceInterface):
    def __init__(self,
                 fragment_repository: FragmentRepositoryInterface,
                 question_publisher: QuestionPublisherInterface,
                 embedder_factory: EmbedderFactory):
        self.fragment_repository = fragment_repository
        self.question_publisher = question_publisher
        self.embedder_factory = embedder_factory

    def process_question(self,
                         question: QuestionRequest,
                         db: Session,
                         embedder_type: str = environment_variables.embedder_type,
                         k: int = 3,
                         threshold: float = 0.3) -> QuestionResponse:
        try:
            embedder = self.embedder_factory.get_embedder(embedder_type)
            embedder_result = embedder.embed_query(question.question)

            fragments = self.fragment_repository.get_most_similar(query_vector=embedder_result,
                                                                  db=db,
                                                                  k=k,
                                                                  threshold=threshold)

            logger.info("Relevant fragments retrieved", extra={"count": len(fragments)})

            fragments_response = ""
            for fragment in fragments:
                fragments_response += fragment.content

            question = QuestionResponse(question=question.question,
                                    context=fragments_response,
                                    messages=question.messages)

            self.question_publisher.publish_question(question)

            return question

        except Exception as e:
            logger.exception("Error in retrieval process")
            raise DatabaseError("Error al procesar la recuperación de fragmentos") from e
