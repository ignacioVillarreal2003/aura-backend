from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.domain.models.document import Document
from app.application.exceptions.exceptions import DatabaseError


logger = logging.getLogger(__name__)


class DocumentRepository:
    def create(self,
               document: Document,
               db: Session) -> Document:
        try:
            logger.debug("Creating document in database")
            db.add(document)
            db.commit()
            db.refresh(document)

            logger.info(
                "Document created in database successfully",
                extra={"document_id": document.id}
            )

            return document

        except Exception as e:
            db.rollback()
            logger.exception("Failed to create document in database")
            raise DatabaseError("Failed to create document in database") from e

    def get_by_id(self,
                  document_id: int,
                  db: Session) -> Optional[Document]:
        try:
            logger.debug("Fetching document by ID", extra={"document_id": document_id})

            document = db.query(Document).filter(Document.id == document_id).first()

            if document:
                logger.debug(
                    "Document found",
                    extra={"document_id": document_id}
                )
            else:
                logger.debug(
                    "Document not found",
                    extra={"document_id": document_id}
                )

            return document

        except Exception as e:
            logger.exception("Failed to fetch document by ID")
            raise DatabaseError("Failed to fetch document from database") from e

    def get_all(self,
                db: Session,
                skip: int = 0,
                limit: int = 100) -> list[type[Document]]:
        try:
            logger.debug(
                "Fetching documents",
                extra={"skip": skip, "limit": limit}
            )

            documents = db.query(Document).offset(skip).limit(limit).all()

            logger.debug(
                "Documents fetched successfully",
                extra={"count": len(documents)}
            )

            return documents

        except Exception as e:
            logger.exception("Failed to fetch documents")
            raise DatabaseError("Failed to fetch documents from database") from e

    def update(self, document: Document, db: Session) -> Document:
        try:
            logger.debug(
                "Updating document in database",
                extra={"document_id": document.id}
            )

            db.merge(document)
            db.commit()
            db.refresh(document)

            logger.info(
                "Document updated successfully",
                extra={"document_id": document.id}
            )

            return document

        except Exception as e:
            db.rollback()
            logger.exception("Failed to update document")
            raise DatabaseError("Failed to update document in database") from e

    def delete(self, document_id: int, db: Session) -> bool:
        try:
            logger.debug(
                "Deleting document from database",
                extra={"document_id": document_id}
            )

            document = db.query(Document).filter(Document.id == document_id).first()

            if not document:
                logger.warning(
                    "Document not found for deletion",
                    extra={"document_id": document_id}
                )
                return False

            db.delete(document)
            db.commit()

            logger.info(
                "Document deleted successfully",
                extra={"document_id": document_id}
            )

            return True

        except Exception as e:
            db.rollback()
            logger.exception("Failed to delete document")
            raise DatabaseError("Failed to delete document from database") from e

    def exists(self, document_id: int, db: Session) -> bool:
        try:
            exists = db.query(Document.id).filter(Document.id == document_id).first() is not None
            logger.debug(
                "Document existence check",
                extra={"document_id": document_id, "exists": exists}
            )
            return exists

        except Exception as e:
            logger.exception("Failed to check document existence")
            raise DatabaseError("Failed to check document existence") from e