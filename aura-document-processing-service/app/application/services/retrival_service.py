from sqlalchemy.orm import Session
import logging
from typing import List

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.configuration.environment_variables import environment_variables
from app.domain.models.fragment import Fragment
from app.application.exceptions.exceptions import DatabaseError
from app.infrastructure.persistence.repositories.interfaces.fragment_repository_interface import \
    FragmentRepositoryInterface

logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(self,
                 fragment_repository: FragmentRepositoryInterface):
        self.fragment_repository = fragment_repository
        self.embedder_factory = EmbedderFactory()

    def process_question(self,
                         question: str,
                         db: Session,
                         embedder_type: str = environment_variables.embedder_type,
                         k: int = 3,
                         threshold: float = 0.3) -> List[Fragment]:
        try:
            embedder = self.embedder_factory.get_embedder(embedder_type)
            embedder_result = embedder.embed_query(question)

            fragments = self.fragment_repository.get_most_similar(query_vector=embedder_result,
                                                                  db=db,
                                                                  k=k,
                                                                  threshold=threshold)

            logger.info("Fragmentos relevantes recuperados", extra={"count": len(fragments)})
            return fragments

        except Exception as e:
            logger.exception("Error en el proceso de recuperación")
            raise DatabaseError("Error al procesar la recuperación de fragmentos") from e
