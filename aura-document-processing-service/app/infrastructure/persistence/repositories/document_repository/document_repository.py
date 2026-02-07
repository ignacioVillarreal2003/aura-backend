from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional, List
import logging

from app.domain.models.document import Document
from app.infrastructure.persistence.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.repositories.exceptions.database_exceptions import DatabaseError

logger = logging.getLogger(__name__)


class DocumentRepository(DocumentRepositoryInterface):
    def create_document(
            self,
            document: Document,
            db: Session
    ) -> Document:
        try:
            logger.debug("Creating document in database")

            db.add(document)
            db.commit()
            db.refresh(document)

            logger.info(f"Document created successfully with ID: {document.id}")

            return document

        except Exception as e:
            db.rollback()
            logger.exception("Failed to create document in database")
            raise DatabaseError("Error al crear documento en la base de datos") from e

    def get_document_by_id(
            self,
            document_id: int,
            db: Session
    ) -> Optional[Document]:
        try:
            logger.debug(f"Fetching document by ID: {document_id}")

            document = db.query(Document).filter(Document.id == document_id).first()

            if document:
                logger.debug(f"Document found with ID: {document_id}")
            else:
                logger.debug(f"Document not found with ID: {document_id}")

            return document

        except Exception as e:
            logger.exception(f"Failed to fetch document by ID: {document_id}")
            raise DatabaseError("Error al obtener documento de la base de datos") from e

    def get_documents(
            self,
            page: Optional[int] = 0,
            size: Optional[int] = 10,
            db: Session = None,
    ) -> List[Document]:
        try:
            logger.debug(f"Fetching documents - page: {page}, size: {size}")

            offset = page * size if page and size else 0

            query = db.query(Document)

            if offset:
                query = query.offset(offset)

            if size:
                query = query.limit(size)

            documents = query.all()

            logger.debug(f"Documents fetched successfully. Count: {len(documents)}")

            return documents

        except Exception as e:
            logger.exception("Failed to fetch documents")
            raise DatabaseError("Error al obtener documentos de la base de datos") from e

    def hard_delete_document_by_id(
            self,
            document_id: int,
            db: Session
    ) -> bool:
        try:
            logger.debug(f"Deleting document with ID: {document_id}")

            document = db.query(Document).filter(Document.id == document_id).first()

            if not document:
                logger.warning(f"Document not found for deletion with ID: {document_id}")
                return False

            db.delete(document)
            db.commit()

            logger.info(f"Document deleted successfully with ID: {document_id}")

            return True

        except Exception as e:
            db.rollback()
            logger.exception(f"Failed to delete document with ID: {document_id}")
            raise DatabaseError("Error al eliminar documento de la base de datos") from e

    def soft_delete_document_by_id(
            self,
            document_id: int,
            db: Session
    ) -> bool:
        try:
            logger.debug(f"Soft deleting document with ID: {document_id}")

            document = db.query(Document).filter(Document.id == document_id).first()

            if not document:
                logger.warning(f"Document not found for soft delete with ID: {document_id}")
                return False

            document.deleted_by = 1
            document.deleted_at = datetime.now()

            db.commit()
            db.refresh(document)

            logger.info(f"Document soft deleted successfully with ID: {document_id}")
            return True

        except Exception as e:
            db.rollback()
            logger.exception(f"Failed to soft delete document with ID: {document_id}")
            raise DatabaseError("Error al actualizar documento en la base de datos") from e

    def update_document(
            self,
            document: Document,
            db: Session
    ) -> Document:
        try:
            logger.debug(f"Updating document with ID: {document.id}")

            existing_document = db.query(Document).filter(
                Document.id == document.id
            ).first()

            if not existing_document:
                logger.warning(f"Document not found for update with ID: {document.id}")
                raise DatabaseError(f"Documento con ID {document.id} no encontrado")

            existing_document.status = document.status
            existing_document.updated_at = datetime.now()

            db.commit()
            db.refresh(existing_document)

            logger.info(f"Document updated successfully with ID: {document.id}")

            return existing_document

        except DatabaseError:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.exception(f"Failed to update document with ID: {document.id}")
            raise DatabaseError("Error al actualizar documento en la base de datos") from e