from sqlalchemy.orm import Session
import logging

from app.domain.models.document import Document
from app.application.exceptions.exceptions import DatabaseError


logger = logging.getLogger(__name__)


class DocumentRepository:

    @staticmethod
    def create(db: Session, document: Document) -> Document:
        try:
            logger.debug("Committing document to database")
            db.add(document)
            db.commit()
            db.refresh(document)
            logger.info("Document created in database", extra={"document_id": document.id})
            return document
        except Exception as e:
            db.rollback()
            logger.exception("Failed to create document in database")
            raise DatabaseError("Failed to create document in database") from e
