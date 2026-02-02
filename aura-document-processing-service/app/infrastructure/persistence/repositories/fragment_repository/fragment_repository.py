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
    def create(
            self,
            fragment: Fragment,
            db: Session
    ) -> Fragment:
        try:
            logger.debug("Creating fragment in database")
            db.add(fragment)
            db.commit()
            db.refresh(fragment)
            logger.info("Fragment created successfully")
            return fragment
        except Exception as e:
            db.rollback()
            logger.exception("Failed to create fragment in database")
            raise DatabaseError("Error al crear fragmento en la base de datos") from e

    def get_by_id(
            self,
            fragment_id: int,
            db: Session
    ) -> Optional[Fragment]:
        try:
            logger.debug("Fetching fragment by ID")
            fragment = db.query(Fragment).filter(Fragment.id == fragment_id).first()

            if fragment:
                logger.debug("Fragment found")
            else:
                logger.debug("Fragment not found")

            return fragment
        except Exception as e:
            logger.exception("Failed to fetch fragment by ID")
            raise DatabaseError("Error al obtener fragmento de la base de datos") from e

    def get_all(
            self,
            db: Session,
            skip: Optional[int] = 0,
            limit: Optional[int] = 100
    ) -> list[Fragment]:
        try:
            logger.debug("Fetching fragments")
            fragments = db.query(Fragment).offset(skip).limit(limit).all()
            logger.debug("Fragments fetched successfully")
            return fragments
        except Exception as e:
            logger.exception("Failed to fetch fragments")
            raise DatabaseError("Error al obtener fragmentos de la base de datos") from e

    def get_by_document_id(
            self,
            document_id: int,
            db: Session
    ) -> list[Fragment]:
        try:
            logger.debug("Fetching fragments by document ID")
            fragments = db.query(Fragment).filter(Fragment.document_id == document_id).all()
            logger.debug("Fragments fetched successfully")
            return fragments
        except Exception as e:
            logger.exception("Failed to fetch fragments by document ID")
            raise DatabaseError("Error al obtener fragmentos por ID de documento") from e

    def get_most_similar(
            self,
            query_vector: list[float],
            db: Session,
            k: Optional[int] = 3,
            threshold: Optional[float] = 0.3
    ) -> List[Fragment]:
        try:
            logger.debug("Executing vector search")

            query_vector_str = "[" + ",".join(map(str, query_vector)) + "]"

            sql = text(f"""
                       SELECT id,
                              document_id,
                              content,
                              1 - (vector <=> '{query_vector_str}') AS cosine_similarity
                       FROM fragment
                       WHERE vector IS NOT NULL
                         AND 1 - (vector <=> '{query_vector_str}') >= :threshold
                       ORDER BY cosine_similarity DESC
                       LIMIT :k
            """)

            results = db.execute(sql, {"k": k, "threshold": threshold}).fetchall()

            logger.info("Vector search completed")

            fragments = []
            for row in results:
                fragments.append(Fragment(
                    id=row.id,
                    document_id=row.document_id,
                    content=row.content
                ))

            return fragments

        except Exception as e:
            logger.exception("Error during vector search")
            raise DatabaseError("Error al ejecutar búsqueda vectorial en pgvector") from e

    def update(
            self,
            fragment: Fragment,
            db: Session
    ) -> Fragment:
        try:
            logger.debug("Updating fragment in database")
            db.merge(fragment)
            db.commit()
            db.refresh(fragment)
            logger.info("Fragment updated successfully")
            return fragment
        except Exception as e:
            db.rollback()
            logger.exception("Failed to update fragment in database")
            raise DatabaseError("Error al actualizar fragmento en la base de datos") from e

    def delete(
            self,
            fragment_id: int,
            db: Session
    ) -> bool:
        try:
            logger.debug("Deleting fragment from database")
            fragment = db.query(Fragment).filter(Fragment.id == fragment_id).first()

            if not fragment:
                logger.warning("Fragment not found for deletion")
                return False

            db.delete(fragment)
            db.commit()
            logger.info("Fragment deleted successfully")
            return True
        except Exception as e:
            db.rollback()
            logger.exception("Failed to delete fragment from database")
            raise DatabaseError("Error al eliminar fragmento de la base de datos") from e

    def exists(
            self,
            fragment_id: int,
            db: Session
    ) -> bool:
        try:
            exists = db.query(Fragment.id).filter(Fragment.id == fragment_id).first() is not None
            logger.debug("Fragment existence check")
            return exists
        except Exception as e:
            logger.exception("Failed to check fragment existence")
            raise DatabaseError("Error al verificar existencia del fragmento en la base de datos") from e
