from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging

from app.domain.models.document import Document
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import DatabaseException

logger = logging.getLogger(__name__)


class DocumentRepository(DocumentRepositoryInterface):
    async def create_document(
            self,
            document: Document,
            database_session: AsyncSession
    ) -> Document:
        try:
            logger.debug("Creating document in database")

            database_session.add(document)
            await database_session.commit()
            await database_session.refresh(document)

            logger.info(f"Document created successfully")

            return document

        except Exception as e:
            await database_session.rollback()
            logger.exception("Failed to create document in database")
            raise DatabaseException("Error creating document in the database") from e

    async def get_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> Optional[Document]:
        try:
            logger.debug("Fetching document by id")

            result = await database_session.execute(
                select(Document).filter(
                    Document.id == document_id
                )
            )
            document = result.scalars().first()

            if document:
                logger.debug("Document found")
            else:
                logger.debug(f"Document not found")

            return document

        except Exception as e:
            logger.exception("Failed to fetch document by id")
            raise DatabaseException("Error fetching document from the database") from e

    async def get_documents(
            self,
            page: Optional[int] = 0,
            size: Optional[int] = 10,
            database_session: AsyncSession = None
    ) -> List[Document]:
        try:
            logger.debug("Fetching documents")

            offset = page * size if page and size else 0

            query = select(Document)

            if offset:
                query = query.offset(offset)

            if size:
                query = query.limit(size)

            result = await database_session.execute(query)
            documents = result.scalars().all()

            logger.debug(f"Documents fetched successfully.")

            return list(documents)

        except Exception as e:
            logger.exception("Failed to fetch documents")
            raise DatabaseException("Error fetching documents from the database") from e

    async def hard_delete_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> bool:
        try:
            logger.debug("Deleting document with id")

            result = await database_session.execute(
                select(Document).filter(
                    Document.id == document_id
                )
            )
            document = result.scalars().first()

            if not document:
                logger.warning("Document not found for deletion")
                return False

            await database_session.delete(document)
            await database_session.commit()

            logger.info("Document deleted successfully")

            return True

        except Exception as e:
            await database_session.rollback()
            logger.exception("Failed to delete document")
            raise DatabaseException("Error deleting document from the database") from e

    async def soft_delete_document_by_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> bool:
        try:
            logger.debug("Soft deleting document by id")

            result = await database_session.execute(
                select(Document).filter(
                    Document.id == document_id
                )
            )
            document = result.scalars().first()

            if not document:
                logger.warning("Document not found")
                return False

            document.deleted_by = user_id
            document.deleted_at = datetime.now()

            await database_session.commit()
            await database_session.refresh(document)

            logger.info("Document soft deleted successfully")
            return True

        except Exception as e:
            await database_session.rollback()
            logger.exception("Failed to delete fragments from database")
            raise DatabaseException("Error deleting fragments from the database") from e

    async def update_document(
            self,
            document: Document,
            database_session: AsyncSession
    ) -> Document:
        try:
            logger.debug("Updating document")

            updated_document = await database_session.merge(document)

            updated_document.updated_at = datetime.now()
            updated_document.updated_by = 0

            await database_session.commit()
            await database_session.refresh(updated_document)

            logger.info(f"Document updated successfully")

            return updated_document

        except Exception as e:
            await database_session.rollback()
            logger.exception(f"Failed to update document")
            raise DatabaseException("Error updating document in the database") from e
