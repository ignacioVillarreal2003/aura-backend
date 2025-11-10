from sqlalchemy.orm import Session
import logging

from app.domain.models.document import Document
from app.application.exceptions.exceptions import DatabaseError
from app.infrastructure.persistence.repositories.interfaces.document_repository_interface import DocumentRepositoryInterface


logger = logging.getLogger(__name__)


class DocumentRepository(DocumentRepositoryInterface):
    def create(self,
               document: Document,
               db: Session) -> Document:
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