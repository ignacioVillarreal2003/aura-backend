from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional, List
import logging

from app.domain.models.fragment import Fragment
from app.infrastructure.persistence.repositories.exceptions.database_exceptions import DatabaseError
from app.infrastructure.persistence.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class FragmentRepository(FragmentRepositoryInterface):
    def create_fragments(
            self,
            fragments: List[Fragment],
            db: Session
    ) -> List[Fragment]:
        try:
            logger.debug("Creating fragments in database")

            db.add_all(fragments)
            db.commit()

            for fragment in fragments:
                db.refresh(fragment)

            logger.info(f"Created {len(fragments)} fragments successfully")
            return fragments

        except Exception as e:
            db.rollback()
            logger.exception("Failed to create fragments in database")
            raise DatabaseError("Error al crear fragmentos en la base de datos") from e

    def get_fragments_by_document_id(
            self,
            document_id: int,
            db: Session
    ) -> List[Fragment]:
        try:
            logger.debug(f"Fetching fragments by document ID: {document_id}")

            fragments = db.query(Fragment).filter(
                Fragment.document_id == document_id
            ).all()

            logger.debug(f"Fetched {len(fragments)} fragments successfully")
            return fragments

        except Exception as e:
            logger.exception("Failed to fetch fragments by document ID")
            raise DatabaseError("Error al obtener fragmentos por ID de documento") from e

    def get_most_similar_fragments(
            self,
            query_vector: List[float],
            db: Session,
            k: Optional[int] = 3,
            threshold: Optional[float] = 0.3
    ) -> List[Fragment]:
        try:
            logger.debug("Executing vector search")

            if not all(isinstance(x, (int, float)) for x in query_vector):
                raise ValueError("query_vector debe contener solo números")

            query_vector_str = "[" + ",".join(str(float(x)) for x in query_vector) + "]"

            sql = text("""
                       SELECT id,
                              document_id,
                              content,
                              1 - (vector <=> :query_vector::vector) AS cosine_similarity
                       FROM fragment
                       WHERE vector IS NOT NULL
                         AND 1 - (vector <=> :query_vector::vector) >= :threshold
                       ORDER BY cosine_similarity DESC LIMIT :k
                       """)

            results = db.execute(
                sql,
                {
                    "query_vector": query_vector_str,
                    "k": k,
                    "threshold": threshold
                }
            ).fetchall()

            logger.info(f"Vector search completed. Found {len(results)} fragments")

            fragments = []
            for row in results:
                fragments.append(Fragment(
                    id=row.id,
                    document_id=row.document_id,
                    content=row.content
                ))

            return fragments

        except ValueError as ve:
            logger.error(f"Invalid query vector: {ve}")
            raise DatabaseError("Vector de búsqueda inválido") from ve
        except Exception as e:
            logger.exception("Error during vector search")
            raise DatabaseError("Error al ejecutar búsqueda vectorial en pgvector") from e

    def hard_delete_fragments_by_document_id(
            self,
            document_id: int,
            db: Session
    ) -> bool:
        try:
            logger.debug(f"Deleting fragments for document ID: {document_id}")

            fragments = db.query(Fragment).filter(
                Fragment.document_id == document_id
            ).all()

            if not fragments:
                logger.warning(f"No fragments found for document ID: {document_id}")
                return False

            for fragment in fragments:
                db.delete(fragment)

            db.commit()
            logger.info(f"Deleted {len(fragments)} fragments successfully")
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Failed to delete fragments from database")
            raise DatabaseError("Error al eliminar fragmentos de la base de datos") from e

    def soft_delete_fragments_by_document_id(
            self,
            document_id: int,
            db: Session
    ) -> bool:
        try:
            logger.debug(f"Soft deleting fragments for document ID: {document_id}")

            fragments = db.query(Fragment).filter(
                Fragment.document_id == document_id
            ).all()

            if not fragments:
                logger.warning(f"No fragments found for document ID: {document_id}")
                return False

            for fragment in fragments:
                fragment.deleted_by = 1
                fragment.deleted_at = datetime.now()

            db.commit()

            logger.info(f"Soft deleted {len(fragments)} fragments successfully")
            return True

        except Exception as e:
            db.rollback()
            logger.exception("Failed to soft delete fragments from database")
            raise DatabaseError("Error al actualizar fragmentos en la base de datos") from e
