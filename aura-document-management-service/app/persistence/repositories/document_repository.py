from sqlalchemy.orm import Session
import logging

from app.domain.models.document import Document
from app.domain.models.document_orm import DocumentORM
from app.application.exceptions.exceptions import DatabaseError


logger = logging.getLogger(__name__)


class DocumentRepository:

    @staticmethod
    def create(db: Session, document: Document) -> DocumentORM:
        try:
            logger.debug("Creating DocumentORM entity")
            db_document = DocumentORM(
                title=document.title,
                type=document.type,
                status=document.status,
                path=document.path,
                size=document.size,
                created_by=document.created_by,
                embedding_status=document.embedding_status,
                vector_count=document.vector_count,
                hash=document.hash
            )

            db.add(db_document)
            logger.debug("Committing document to database")
            db.commit()
            db.refresh(db_document)
            logger.info("Document created in database", extra={"document_id": db_document.id})
            return db_document
        except Exception as e:
            db.rollback()
            logger.exception("Failed to create document in database")
            raise DatabaseError("Failed to create document in database") from e
