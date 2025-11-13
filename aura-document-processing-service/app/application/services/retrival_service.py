from sqlalchemy.orm import Session
import logging
from typing import List

from app.application.processors.embeddings.embeddings_factory import EmbeddingsFactory
from app.domain.models.fragment import Fragment
from app.infrastructure.persistence.repositories.fragment_repository import FragmentRepository
from app.application.exceptions.exceptions import DatabaseError


logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(self, fragment_repository: FragmentRepository):
        self.fragment_repository = fragment_repository
        self.embedding_factory = EmbeddingsFactory()

    def process_question(
        self,
        question: str,
        db: Session,
        embedding_type: str = "huggingface",
        k: int = 5,
    ) -> List[Fragment]:
        try:
            embedding_model = self.embedding_factory.get_embedding(embedding_type)
            question_vector = embedding_model.embed_query(question)

            logger.info("Embedding generado", extra={"embedding_type": embedding_type})

            fragments = self.fragment_repository.get_most_similar(
                query_vector=question_vector,
                k=k,
                db=db
            )

            logger.info("Fragmentos relevantes recuperados", extra={"count": len(fragments)})
            return fragments

        except Exception as e:
            logger.exception("Error en el proceso de recuperación")
            raise DatabaseError("Error al procesar la recuperación de fragmentos") from e
