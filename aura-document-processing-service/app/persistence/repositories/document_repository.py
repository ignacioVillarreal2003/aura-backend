from typing import Optional
import logging

from sqlalchemy.orm import Session

from app.domain.models.document_orm import DocumentORM
from app.application.exceptions.exceptions import DatabaseError


logger = logging.getLogger(__name__)


class DocumentRepository:

    @staticmethod
    def get_by_id(db: Session, document_id: int) -> Optional[DocumentORM]:
        try:
            logger.debug("Fetching DocumentORM by id", extra={"document_id": document_id})
            return db.query(DocumentORM).filter(DocumentORM.id == document_id).first()
        except Exception as e:
            logger.exception("Failed to fetch document by id")
            raise DatabaseError("Failed to fetch document by id") from e


