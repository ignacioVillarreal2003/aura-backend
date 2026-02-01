from sqlalchemy.orm import Session
from typing import Optional
import logging

from app.domain.models.document import Document
from app.application.exceptions.app_exception import DatabaseError
from app.infrastructure.persistence.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)

logger = logging.getLogger(__name__)


class DocumentRepository(DocumentRepositoryInterface):
    def create(
            self,
            document: Document,
            db: Session
    ) -> Document:
        try:
            logger.debug("Creating document in database")

            db.add(document)
            db.commit()
            db.refresh(document)

            logger.info("Document created in database successfully")

            return document

        except Exception as e:
            db.rollback()
            logger.exception("Failed to create document in database")
            raise DatabaseError("Error al crear documento en la base de datos") from e

    def get_by_id(
            self,
            document_id: int,
            db: Session
    ) -> Optional[Document]:
        try:
            logger.debug("Fetching document by ID")

            document = db.query(Document).filter(Document.id == document_id).first()

            if document:
                logger.debug("Document found")
            else:
                logger.debug("Document not found")

            return document

        except Exception as e:
            logger.exception("Failed to fetch document by ID")
            raise DatabaseError("Error al obtener documento de la base de datos") from e

    def get_all(
            self,
            db: Session,
            skip: int = 0,
            limit: int = 100
    ) -> list[Document]:
        try:
            logger.debug("Fetching documents")

            documents = db.query(Document).offset(skip).limit(limit).all()

            logger.debug("Documents fetched successfully")

            return documents

        except Exception as e:
            logger.exception("Failed to fetch documents")
            raise DatabaseError("Error al obtener documentos de la base de datos") from e

    def update(
            self,
            document: Document,
            db: Session
    ) -> Document:
        try:
            logger.debug("Updating document in database")

            db.merge(document)
            db.commit()
            db.refresh(document)

            logger.info("Document updated successfully")

            return document

        except Exception as e:
            db.rollback()
            logger.exception("Failed to update document")
            raise DatabaseError("Error al actualizar documento en la base de datos") from e

    def delete(
            self,
            document_id: int,
            db: Session
    ) -> bool:
        try:
            logger.debug("Deleting document from database")

            document = db.query(Document).filter(Document.id == document_id).first()

            if not document:
                logger.warning("Document not found for deletion")
                return False

            db.delete(document)
            db.commit()

            logger.info("Document deleted successfully")

            return True

        except Exception as e:
            db.rollback()
            logger.exception("Failed to delete document")
            raise DatabaseError("Error al eliminar documento de la base de datos") from e

    def exists(
            self,
            document_id: int,
            db: Session
    ) -> bool:
        try:
            exists = db.query(Document.id).filter(Document.id == document_id).first() is not None
            logger.debug("Document existence check")
            return exists

        except Exception as e:
            logger.exception("Failed to check document existence")
            raise DatabaseError("Error al verificar existencia del documento") from e
