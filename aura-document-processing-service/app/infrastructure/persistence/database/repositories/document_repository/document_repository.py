import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.constants.document.document_type import DocumentType
from app.domain.models.document import Document
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import (
    DatabaseConstraintViolationException,
    DatabaseException
)

logger = logging.getLogger(__name__)


class DocumentRepository(DocumentRepositoryInterface):
    async def get_documents_by_ids(
            self,
            document_ids: List[int],
            database_session: AsyncSession
    ) -> List[Document]:
        try:
            logger.debug(
                "Fetching document by IDs",
                extra={"document_ids_count": len(document_ids)}
            )
            result = await database_session.execute(
                select(Document).where(Document.id.in_(document_ids))
            )
            documents = list(result.scalars().all())
            logger.debug(
                "Documents by IDs lookup completed",
                extra={"document_ids_count": len(document_ids), "found_count": len(documents)}
            )
            return documents
        except Exception as e:
            raise DatabaseException("Error fetching document by IDs from the database") from e

    async def get_documents_missing_metadata(
            self,
            database_session: AsyncSession
    ) -> List[Document]:
        try:
            logger.debug("Fetching documents missing metadata")

            result = await database_session.execute(
                select(Document).where(
                    Document.deleted_at.is_(None),
                    or_(
                        Document.type.is_(None),
                        Document.category.is_(None),
                        Document.description.is_(None)
                    )
                )
            )
            documents = list(result.scalars().all())

            logger.debug(
                "Documents missing metadata fetched",
                extra={"count": len(documents)}
            )
            return documents

        except Exception as e:
            raise DatabaseException(
                "Error fetching documents missing metadata from the database"
            ) from e

    async def get_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> Optional[Document]:
        try:
            logger.debug("Fetching document by ID", extra={"document_id": document_id})

            result = await database_session.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalars().first()

            logger.debug(
                "Document lookup completed",
                extra={"document_id": document_id, "found": document is not None}
            )
            return document

        except Exception as e:
            raise DatabaseException("Error fetching document from the database") from e

    async def update_document(
            self,
            document: Document,
            database_session: AsyncSession
    ) -> Document:
        try:
            logger.debug("Updating document", extra={"document_id": document.id})

            updated_document = await database_session.merge(document)
            await database_session.flush()
            await database_session.refresh(updated_document)

            logger.info(
                "Document updated successfully",
                extra={"document_id": updated_document.id}
            )
            return updated_document

        except IntegrityError as e:
            raise DatabaseConstraintViolationException(
                "Constraint violation updating document"
            ) from e
        except Exception as e:
            raise DatabaseException("Error updating document in the database") from e







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

            logger.info("Document created successfully", extra={"document_id": document.id})
            return document

        except IntegrityError as e:
            raise DatabaseConstraintViolationException(
                "Constraint violation creating document"
            ) from e
        except Exception as e:
            logger.exception("Failed to create document in database")
            raise DatabaseException("Error creating document in the database") from e


    async def get_documents_by_chat_id(
            self,
            chat_id: int,
            database_session: AsyncSession
    ) -> List[Document]:
        try:
            logger.debug("Fetching documents by chat ID", extra={"chat_id": chat_id})

            result = await database_session.execute(
                select(Document).where(
                    Document.chat_id == chat_id,
                    Document.deleted_at.is_(None),
                )
            )
            documents = list(result.scalars().all())

            logger.debug(
                "Documents by chat lookup completed",
                extra={"chat_id": chat_id, "count": len(documents)}
            )
            return documents

        except Exception as e:
            raise DatabaseException(
                "Error fetching documents by chat ID from the database"
            ) from e

    async def get_documents(
            self,
            database_session: AsyncSession,
            page: Optional[int] = None,
            size: Optional[int] = None,
            name: Optional[str] = None,
            description: Optional[str] = None,
            category: Optional[str] = None,
            type: Optional[DocumentType] = None,
            created_from: Optional[datetime] = None,
            created_to: Optional[datetime] = None,
    ) -> List[Document]:
        try:
            logger.debug(
                "Searching documents",
                extra={
                    "page": page, "size": size, "name": name,
                    "description": description, "category": category,
                    "type": type, "created_from": created_from, "created_to": created_to
                }
            )

            query = select(Document).where(Document.deleted_at.is_(None))

            if name is not None:
                query = query.where(Document.name.ilike(f"%{name}%"))
            if description is not None:
                query = query.where(Document.description.ilike(f"%{description}%"))
            if category is not None:
                query = query.where(Document.category.ilike(f"%{category}%"))
            if type is not None:
                query = query.where(Document.type == type)
            if created_from is not None:
                query = query.where(Document.created_at >= created_from)
            if created_to is not None:
                query = query.where(Document.created_at <= created_to)

            if page is not None and size is not None:
                query = query.offset(page * size).limit(size)
            elif size is not None:
                query = query.limit(size)

            result = await database_session.execute(query)
            documents = list(result.scalars().all())

            logger.debug(
                "Documents search completed",
                extra={"count": len(documents)}
            )
            return documents

        except Exception as e:
            raise DatabaseException("Error searching documents in the database") from e


    async def hard_delete_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> bool:
        try:
            logger.debug("Hard-deleting document", extra={"document_id": document_id})

            result = await database_session.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalars().first()

            if document is None:
                logger.warning(
                    "Document not found for hard-delete",
                    extra={"document_id": document_id}
                )
                return False

            await database_session.delete(document)
            await database_session.flush()

            logger.info("Document hard-deleted successfully", extra={"document_id": document_id})
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
                extra={"document_id": document_id, "user_id": user_id}
            )

            result = await database_session.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.deleted_at.is_(None)
                )
            )
            document = result.scalars().first()

            if document is None:
                logger.warning(
                    "Document not found or already deleted for soft-delete",
                    extra={"document_id": document_id}
                )
                return False

            document.deleted_by = user_id
            document.deleted_at = datetime.now(timezone.utc)

            await database_session.flush()
            await database_session.refresh(document)

            logger.info(
                "Document soft-deleted successfully",
                extra={"document_id": document_id, "user_id": user_id}
            )
            return True

        except Exception as e:
            raise DatabaseException("Error soft-deleting document from the database") from e
