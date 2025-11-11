from typing import Optional
import logging
from sqlalchemy.orm import Session

from app.application.exceptions.exceptions import DatabaseError
from app.domain.models.document import Document
from app.infrastructure.persistence.repositories.interfaces.document_repository_interface import DocumentRepositoryInterface


logger = logging.getLogger(__name__)


class DocumentRepository(DocumentRepositoryInterface):
    def get_by_id(self,
                  document_id: int,
                  db: Session) -> Optional[Document]:
        try:
            logger.debug("Fetching document by id", extra={"document_id": document_id})
            return db.query(Document).filter(Document.id == document_id).first()
        except Exception as e:
            logger.exception("Failed to fetch document by id")
            raise DatabaseError("Failed to fetch document by id") from e