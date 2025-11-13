from sqlalchemy import text, select
from sqlalchemy.orm import Session
from typing import Optional, List, Any
import logging

from app.domain.models.fragment import Fragment
from app.application.exceptions.exceptions import DatabaseError


logger = logging.getLogger(__name__)


class FragmentRepository:
    def create(self, fragment: Fragment, db: Session) -> Fragment:
        try:
            logger.debug("Creating fragment in database", extra={"document_id": fragment.document_id})
            db.add(fragment)
            db.commit()
            db.refresh(fragment)
            logger.info("Fragment created successfully", extra={"fragment_id": fragment.id})
            return fragment
        except Exception as e:
            db.rollback()
            logger.exception("Failed to create fragment in database")
            raise DatabaseError("Failed to create fragment in database") from e

    def get_by_id(self, fragment_id: int, db: Session) -> Optional[Fragment]:
        try:
            logger.debug("Fetching fragment by ID", extra={"fragment_id": fragment_id})
            fragment = db.query(Fragment).filter(Fragment.id == fragment_id).first()

            if fragment:
                logger.debug("Fragment found", extra={"fragment_id": fragment_id})
            else:
                logger.debug("Fragment not found", extra={"fragment_id": fragment_id})

            return fragment
        except Exception as e:
            logger.exception("Failed to fetch fragment by ID")
            raise DatabaseError("Failed to fetch fragment from database") from e

    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> list[type[Fragment]]:
        try:
            logger.debug("Fetching fragments", extra={"skip": skip, "limit": limit})
            fragments = db.query(Fragment).offset(skip).limit(limit).all()
            logger.debug("Fragments fetched successfully", extra={"count": len(fragments)})
            return fragments
        except Exception as e:
            logger.exception("Failed to fetch fragments")
            raise DatabaseError("Failed to fetch fragments from database") from e

    def get_by_document_id(self, document_id: int, db: Session) -> list[type[Fragment]]:
        try:
            logger.debug("Fetching fragments by document ID", extra={"document_id": document_id})
            fragments = db.query(Fragment).filter(Fragment.document_id == document_id).all()
            logger.debug("Fragments fetched successfully", extra={"document_id": document_id, "count": len(fragments)})
            return fragments
        except Exception as e:
            logger.exception("Failed to fetch fragments by document ID")
            raise DatabaseError("Failed to fetch fragments by document ID") from e

    def get_most_similar(
            self,
            query_vector: list[float],
            k: int,
            db: Session
    ) -> List[Fragment]:
        try:
            logger.debug("Ejecutando búsqueda vectorial", extra={"k": k})

            query_vector_str = "[" + ",".join(map(str, query_vector)) + "]"

            sql = text(f"""
               SELECT id,
                      document_id,
                      content,
                      1 - (vector <=> '{query_vector_str}') AS cosine_similarity
               FROM fragment
               WHERE vector IS NOT NULL
               ORDER BY cosine_similarity DESC LIMIT :k
            """)

            results = db.execute(sql, {"k": k}).fetchall()

            logger.info("Búsqueda vectorial completada", extra={"count": len(results)})

            fragments = [
                Fragment(
                    id=row.id,
                    document_id=row.document_id,
                    content=row.content
                )
                for row in results
            ]

            return fragments

        except Exception as e:
            logger.exception("Error durante la búsqueda vectorial")
            raise DatabaseError("Error al ejecutar búsqueda vectorial en pgvector") from e

    def update(self, fragment: Fragment, db: Session) -> Fragment:
        try:
            logger.debug("Updating fragment in database", extra={"fragment_id": fragment.id})
            db.merge(fragment)
            db.commit()
            db.refresh(fragment)
            logger.info("Fragment updated successfully", extra={"fragment_id": fragment.id})
            return fragment
        except Exception as e:
            db.rollback()
            logger.exception("Failed to update fragment in database")
            raise DatabaseError("Failed to update fragment in database") from e

    def delete(self, fragment_id: int, db: Session) -> bool:
        try:
            logger.debug("Deleting fragment from database", extra={"fragment_id": fragment_id})
            fragment = db.query(Fragment).filter(Fragment.id == fragment_id).first()

            if not fragment:
                logger.warning("Fragment not found for deletion", extra={"fragment_id": fragment_id})
                return False

            db.delete(fragment)
            db.commit()
            logger.info("Fragment deleted successfully", extra={"fragment_id": fragment_id})
            return True
        except Exception as e:
            db.rollback()
            logger.exception("Failed to delete fragment from database")
            raise DatabaseError("Failed to delete fragment from database") from e

    def exists(self, fragment_id: int, db: Session) -> bool:
        try:
            exists = db.query(Fragment.id).filter(Fragment.id == fragment_id).first() is not None
            logger.debug("Fragment existence check", extra={"fragment_id": fragment_id, "exists": exists})
            return exists
        except Exception as e:
            logger.exception("Failed to check fragment existence")
            raise DatabaseError("Failed to check fragment existence in database") from e
