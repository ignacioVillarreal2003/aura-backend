import logging
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.document import Document
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import (
    DatabaseException,
    DatabaseConstraintViolationException
)

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

            await database_session.flush()
            await database_session.refresh(document)

            logger.info(
                "Document created successfully",
                extra={
                    "document_id": document.id
                }
            )
            return document

        except IntegrityError as e:
            raise DatabaseConstraintViolationException("Constraint violation creating document") from e
        except Exception as e:
            logger.exception("Failed to create document in database")
            raise DatabaseException("Error creating document in the database") from e

    async def get_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> Optional[Document]:
        try:
            logger.debug(
                "Fetching document by ID",
                extra={
                    "document_id": document_id
                }
            )

            result = await database_session.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalars().first()

            logger.debug(
                "Document lookup completed",
                extra={
                    "document_id": document_id,
                    "found": document is not None
                }
            )
            return document

        except Exception as e:
            raise DatabaseException("Error fetching document from the database") from e

    async def get_documents_by_chat_id(
            self,
            chat_id: int,
            database_session: AsyncSession
    ) -> List[Document]:
        try:
            logger.debug(
                "Fetching documents by chat ID",
                extra={
                    "chat_id": chat_id
                }
            )

            result = await database_session.execute(
                select(Document).where(Document.chat_id == chat_id)
            )
            documents = list(result.scalars().all())

            logger.debug(
                "Documents by chat lookup completed",
                extra={
                    "chat_id": chat_id,
                    "count": len(documents)
                }
            )
            return documents

        except Exception as e:
            raise DatabaseException("Error fetching documents by chat ID from the database") from e

    async def get_documents(
            self,
            database_session: AsyncSession,
            page: Optional[int] = None,
            size: Optional[int] = None
    ) -> List[Document]:
        try:
            logger.debug(
                "Fetching documents",
                extra={
                    "page": page,
                    "size": size
                }
            )

            query = select(Document)

            if page is not None and size is not None:
                query = query.offset(page * size).limit(size)
            elif size is not None:
                query = query.limit(size)

            result = await database_session.execute(query)
            documents = list(result.scalars().all())

            logger.debug(
                "Documents fetched successfully",
                extra={
                    "page": page,
                    "size": size,
                    "count": len(documents)
                }
            )
            return documents

        except Exception as e:
            raise DatabaseException("Error fetching documents from the database") from e

    async def update_document(
            self,
            document: Document,
            database_session: AsyncSession
    ) -> Document:
        try:
            logger.debug(
                "Updating document",
                extra={
                    "document_id": document.id
                }
            )

            updated_document = await database_session.merge(document)
            await database_session.flush()
            await database_session.refresh(updated_document)

            logger.info(
                "Document updated successfully",
                extra={
                    "document_id": updated_document.id
                }
            )
            return updated_document

        except IntegrityError as e:
            raise DatabaseConstraintViolationException("Constraint violation updating document") from e
        except Exception as e:
            raise DatabaseException("Error updating document in the database") from e

    async def hard_delete_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> bool:
        try:
            logger.debug(
                "Hard-deleting document",
                extra={
                    "document_id": document_id
                }
            )

            result = await database_session.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalars().first()

            if document is None:
                logger.warning(
                    "Document not found for hard-delete",
                    extra={
                        "document_id": document_id
                    }
                )
                return False

            await database_session.delete(document)
            await database_session.flush()

            logger.info(
                "Document hard-deleted successfully",
                extra={
                    "document_id": document_id
                }
            )
            return True

        except Exception as e:
            raise DatabaseException("Error deleting document from the database") from e

    async def soft_delete_document_by_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> bool:
        try:
            logger.debug(
                "Soft-deleting document",
                extra={
                    "document_id": document_id,
                    "user_id": user_id
                }
            )

            result = await database_session.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalars().first()

            if document is None:
                logger.warning(
                    "Document not found for soft-delete",
                    extra={
                        "document_id": document_id
                    }
                )
                return False

            document.deleted_by = user_id
            document.deleted_at = datetime.now(timezone.utc)

            await database_session.flush()
            await database_session.refresh(document)

            logger.info(
                "Document soft-deleted successfully",
                extra={
                    "document_id": document_id,
                    "user_id": user_id
                }
            )
            return True

        except Exception as e:
            raise DatabaseException("Error soft-deleting document from the database") from e
