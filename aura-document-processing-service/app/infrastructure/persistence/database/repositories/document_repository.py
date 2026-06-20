import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import asc, desc, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.constants.document.document_status import DocumentStatus
from app.domain.constants.document.document_type import DocumentType
from app.domain.field_limits import MAX_DOCUMENTS_IN_LIST
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import (
    DatabaseConstraintViolationException,
    DatabaseException,
)
from app.infrastructure.persistence.database.repositories.repository_query_utils import chunked_ids

logger = logging.getLogger(__name__)


class DocumentRepository(DocumentRepositoryInterface):
    async def get_document_by_id(
            self,
            document_id: int,
            database_session: AsyncSession,
    ) -> Optional[Document]:
        try:
            logger.debug(
                "Fetching the document by ID.",
                extra={
                    "document_id": document_id
                }
            )

            result = await database_session.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.deleted_at.is_(None),
                )
            )
            document = result.scalars().first()

            logger.debug(
                "The document lookup completed.",
                extra={
                    "document_id": document_id,
                    "found": document is not None
                }
            )
            return document

        except SQLAlchemyError as e:
            logger.exception(
                "Database error while fetching the document.",
                extra={"document_id": document_id},
            )
            raise DatabaseException("Failed to fetch the document.") from e

    async def get_document_by_id_including_deleted(
            self,
            document_id: int,
            database_session: AsyncSession,
    ) -> Optional[Document]:
        try:
            result = await database_session.execute(
                select(Document).where(Document.id == document_id)
            )
            return result.scalars().first()
        except SQLAlchemyError as e:
            logger.exception(
                "Database error while fetching the document (including deleted).",
                extra={"document_id": document_id},
            )
            raise DatabaseException("Failed to fetch the document.") from e

    async def get_documents_by_chat_id(
            self,
            chat_id: int,
            database_session: AsyncSession,
            page: Optional[int] = None,
            size: Optional[int] = None,
    ) -> list[Document]:
        try:
            paginate = page is not None and size is not None
            logger.debug(
                "Fetching documents by chat ID.",
                extra={
                    "chat_id": chat_id,
                    "page": page,
                    "size": size,
                    "paginated": paginate,
                }
            )

            query = (
                select(Document)
                .where(
                    Document.chat_id == chat_id,
                    Document.deleted_at.is_(None),
                )
                .order_by(desc(Document.created_at), desc(Document.id))
            )

            if paginate:
                query = query.offset((page - 1) * size).limit(size)
            else:
                query = query.limit(MAX_DOCUMENTS_IN_LIST)

            result = await database_session.execute(query)
            documents = list(result.scalars().all())

            logger.debug(
                "The documents-by-chat lookup completed.",
                extra={
                    "chat_id": chat_id,
                    "count": len(documents)
                }
            )
            return documents

        except SQLAlchemyError as e:
            logger.exception(
                "Database error while fetching documents by chat ID.",
                extra={"chat_id": chat_id},
            )
            raise DatabaseException("Failed to fetch documents by chat ID.") from e

    async def get_documents_by_ids(
            self,
            document_ids: list[int],
            database_session: AsyncSession,
    ) -> list[Document]:
        if not document_ids:
            return []
        try:
            logger.debug(
                "Fetching documents by IDs.",
                extra={
                    "document_ids_count": len(document_ids)
                }
            )
            by_id: dict[int, Document] = {}
            for chunk in chunked_ids(document_ids):
                result = await database_session.execute(
                    select(Document).where(
                        Document.id.in_(chunk),
                        Document.deleted_at.is_(None),
                    )
                )
                for row in result.scalars().all():
                    by_id[int(row.id)] = row

            ordered: list[Document] = []
            for doc_id in dict.fromkeys(document_ids):
                if doc_id in by_id:
                    ordered.append(by_id[doc_id])

            logger.debug(
                "The documents-by-IDs lookup completed.",
                extra={
                    "document_ids_count": len(document_ids),
                    "found_count": len(ordered)
                }
            )
            return ordered

        except SQLAlchemyError as e:
            logger.exception(
                "Database error while fetching documents by IDs.",
                extra={"document_ids_count": len(document_ids)},
            )
            raise DatabaseException("Failed to fetch documents by IDs.") from e

    async def get_documents(
            self,
            database_session: AsyncSession,
            page: Optional[int] = None,
            size: Optional[int] = None,
            name: Optional[str] = None,
            description: Optional[str] = None,
            category: Optional[str] = None,
            document_type: Optional[DocumentType] = None,
            created_from: Optional[datetime] = None,
            created_to: Optional[datetime] = None,
    ) -> list[Document]:
        try:
            paginate = page is not None and size is not None
            logger.debug(
                "Searching documents with filters.",
                extra={
                    "page": page,
                    "size": size,
                    "paginated": paginate,
                    "name_filter_set": name is not None,
                    "description_filter_set": description is not None,
                    "category_filter_set": category is not None,
                    "type_filter_set": document_type is not None,
                    "created_range_set": created_from is not None or created_to is not None,
                }
            )

            query = (
                select(Document)
                .where(Document.deleted_at.is_(None))
                .order_by(desc(Document.created_at), desc(Document.id))
            )

            if name is not None:
                query = query.where(Document.name.ilike(f"%{name}%"))
            if description is not None:
                query = query.where(Document.description.ilike(f"%{description}%"))
            if category is not None:
                query = query.where(Document.category.ilike(f"%{category}%"))
            if document_type is not None:
                query = query.where(Document.type == document_type.value)
            if created_from is not None:
                query = query.where(Document.created_at >= created_from)
            if created_to is not None:
                query = query.where(Document.created_at <= created_to)

            if paginate:
                query = query.offset((page - 1) * size).limit(size)
            else:
                query = query.limit(MAX_DOCUMENTS_IN_LIST)

            result = await database_session.execute(query)
            documents = list(result.scalars().all())

            logger.debug(
                "The document search completed.",
                extra={
                    "count": len(documents)
                }
            )
            return documents

        except SQLAlchemyError as e:
            logger.exception(
                "Database error while searching documents.",
                extra={"page": page, "size": size},
            )
            raise DatabaseException("Failed to search documents.") from e

    async def create_document(
            self,
            document: Document,
            database_session: AsyncSession,
    ) -> Document:
        try:
            logger.debug("Creating the document in the database.")

            database_session.add(document)
            await database_session.flush()
            await database_session.refresh(document)

            logger.info(
                "The document was created successfully.",
                extra={
                    "document_id": document.id
                }
            )
            return document

        except IntegrityError as e:
            raise DatabaseConstraintViolationException(
                "A database constraint was violated while creating the document."
            ) from e
        except SQLAlchemyError as e:
            logger.exception("Failed to create the document in the database.")
            raise DatabaseException("Failed to create the document.") from e

    async def update_document(
            self,
            document: Document,
            database_session: AsyncSession,
    ) -> Document:
        try:
            logger.debug(
                "Updating the document.",
                extra={
                    "document_id": document.id
                }
            )

            updated_document = await database_session.merge(document)
            await database_session.flush()
            await database_session.refresh(updated_document)

            logger.info(
                "The document was updated successfully.",
                extra={
                    "document_id": updated_document.id
                }
            )
            return updated_document

        except IntegrityError as e:
            raise DatabaseConstraintViolationException(
                "A database constraint was violated while updating the document."
            ) from e
        except SQLAlchemyError as e:
            logger.exception(
                "Failed to update the document.",
                extra={"document_id": document.id},
            )
            raise DatabaseException("Failed to update the document.") from e

    async def soft_delete_document_by_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession,
            deleted_at: Optional[datetime] = None,
    ) -> bool:
        try:
            logger.debug(
                "Soft-deleting the document.",
                extra={
                    "document_id": document_id,
                    "user_id": user_id
                }
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
                    "No document was found, or it was already deleted, for soft-delete.",
                    extra={
                        "document_id": document_id
                    }
                )
                return False

            document.deleted_by = user_id
            document.deleted_at = deleted_at or datetime.now(timezone.utc)

            await database_session.flush()
            await database_session.refresh(document)

            logger.info(
                "The document was soft-deleted successfully.",
                extra={
                    "document_id": document_id,
                    "user_id": user_id
                }
            )
            return True

        except SQLAlchemyError as e:
            logger.exception(
                "Failed to soft-delete the document.",
                extra={"document_id": document_id, "user_id": user_id},
            )
            raise DatabaseException("Failed to soft-delete the document.") from e

    async def restore_document_by_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession,
    ) -> Optional[Document]:
        try:
            logger.debug(
                "Restoring the document.",
                extra={
                    "document_id": document_id,
                    "user_id": user_id
                }
            )

            result = await database_session.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.deleted_at.is_not(None)
                )
            )
            document = result.scalars().first()

            if document is None:
                logger.warning(
                    "No soft-deleted document was found for restore.",
                    extra={
                        "document_id": document_id
                    }
                )
                return None

            document.deleted_by = None
            document.deleted_at = None
            document.updated_by = user_id
            document.updated_at = datetime.now(timezone.utc)

            await database_session.flush()
            await database_session.refresh(document)

            logger.info(
                "The document was restored successfully.",
                extra={
                    "document_id": document_id,
                    "user_id": user_id
                }
            )
            return document

        except SQLAlchemyError as e:
            logger.exception(
                "Failed to restore the document.",
                extra={"document_id": document_id, "user_id": user_id},
            )
            raise DatabaseException("Failed to restore the document.") from e

    async def get_stale_uploaded_documents(
            self,
            created_before: datetime,
            limit: int,
            database_session: AsyncSession,
    ) -> list[Document]:
        try:
            logger.debug(
                "Fetching stale uploaded documents for outbox reconciliation.",
                extra={"created_before": created_before.isoformat(), "limit": limit},
            )
            result = await database_session.execute(
                select(Document)
                .where(
                    Document.deleted_at.is_(None),
                    Document.status == DocumentStatus.uploaded.value,
                    Document.created_at <= created_before,
                )
                .order_by(asc(Document.created_at))
                .limit(limit)
            )
            documents = list(result.scalars().all())
            logger.debug(
                "Stale uploaded document lookup completed.",
                extra={"count": len(documents)},
            )
            return documents

        except SQLAlchemyError as e:
            logger.exception("Database error while fetching stale uploaded documents.")
            raise DatabaseException("Failed to fetch stale uploaded documents.") from e
