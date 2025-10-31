from sqlalchemy.orm import Session
import logging

from app.domain.models.fragment import Fragment
from app.domain.models.fragment_orm import FragmentORM
from app.application.exceptions.exceptions import DatabaseError


logger = logging.getLogger(__name__)

class FragmentRepository:

    @staticmethod
    def create(db: Session, fragment: Fragment) -> FragmentORM:
        try:
            logger.debug("Creating FragmentORM entity")
            db_fragment = FragmentORM(
                source_document_id=fragment.source_document_id,
                vector=fragment.vector,
                content=fragment.content,
                fragment_index=fragment.fragment_index,
                chunk_size=fragment.chunk_size,
                created_by=fragment.created_by
            )

            db.add(db_fragment)
            logger.debug("Committing fragment to database")
            db.commit()
            db.refresh(db_fragment)
            logger.info("Fragment created in database", extra={"fragment_id": db_fragment.id})
            return db_fragment
        except Exception as e:
            db.rollback()
            logger.exception("Failed to create fragment in database")
            raise DatabaseError("Failed to create fragment in database") from e
