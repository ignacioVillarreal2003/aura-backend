from sqlalchemy.orm import Session
import logging

from app.domain.models.fragment import Fragment
from app.application.exceptions.exceptions import DatabaseError
from app.infrastructure.persistence.repositories.interfaces.fragment_repository_interface import FragmentRepositoryInterface


logger = logging.getLogger(__name__)


class FragmentRepository(FragmentRepositoryInterface):
    def create(self, fragment: Fragment, db: Session) -> Fragment:
        try:
            logger.debug("Committing fragment to database")
            db.add(fragment)
            db.commit()
            db.refresh(fragment)
            logger.info("Fragment created in database", extra={"fragment_id": fragment.id})
            return fragment
        except Exception as e:
            db.rollback()
            logger.exception("Failed to create fragment in database")
            raise DatabaseError("Failed to create fragment in database") from e
