import logging
from typing import Optional
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.orm.document_in_document_collection import DocumentInDocumentCollection
from app.infrastructure.persistence.database.repositories.document_collection_repository.document_collection_repository_interface import (
    DocumentCollectionRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.database_exceptions import DatabaseException
from app.infrastructure.persistence.database.repositories.repository_query_utils import chunked_ids

logger = logging.getLogger(__name__)


class DocumentCollectionRepository(DocumentCollectionRepositoryInterface):
    async def get_accessible_document_ids(
            self,
            user_id: int,
            document_ids: list[int],
            chat_id: Optional[int],
            accessible_collection_ids: frozenset[int],
            database_session: AsyncSession,
    ) -> set[int]:
        if not document_ids:
            return set()

        try:
            accessible: set[int] = set()

            for chunk in chunked_ids(document_ids):
                conditions = [Document.created_by == user_id]
                if chat_id is not None:
                    conditions.append(Document.chat_id == chat_id)

                simple_result = await database_session.execute(
                    select(Document.id).where(
                        Document.id.in_(chunk),
                        Document.deleted_at.is_(None),
                        or_(*conditions),
                    )
                )
                accessible.update(row[0] for row in simple_result)

            remaining_ordered = [did for did in dict.fromkeys(document_ids) if did not in accessible]
            if remaining_ordered and accessible_collection_ids:
                coll_tuple = tuple(accessible_collection_ids)
                if coll_tuple:
                    for chunk in chunked_ids(remaining_ordered):
                        conditions = (
                            DocumentInDocumentCollection.document_id.in_(chunk),
                            DocumentInDocumentCollection.deleted_at.is_(None),
                            DocumentInDocumentCollection.document_collection_id.in_(coll_tuple),
                        )
                        collection_result = await database_session.execute(
                            select(DocumentInDocumentCollection.document_id).where(and_(*conditions))
                        )
                        accessible.update(row[0] for row in collection_result)

            logger.debug(
                "Accessible document IDs resolved.",
                extra={
                    "user_id": user_id,
                    "requested": len(document_ids),
                    "accessible": len(accessible),
                },
            )
            return accessible

        except SQLAlchemyError as e:
            logger.exception(
                "Database error while resolving accessible document IDs.",
                extra={"user_id": user_id, "requested_count": len(document_ids)},
            )
            raise DatabaseException("Failed to resolve accessible document IDs.") from e

    async def list_all_accessible_document_ids(
            self,
            user_id: int,
            database_session: AsyncSession,
            accessible_collection_ids: frozenset[int],
            chat_id: Optional[int] = None,
            limit: int = 10_000,
    ) -> list[int]:
        try:
            owned_conditions = [
                Document.created_by == user_id,
                Document.deleted_at.is_(None),
            ]
            if chat_id is not None:
                owned_conditions.append(Document.chat_id == chat_id)

            owned_result = await database_session.execute(
                select(Document.id)
                .where(*owned_conditions)
                .order_by(Document.id)
                .limit(limit)
            )
            accessible: set[int] = {row[0] for row in owned_result}

            remaining = max(0, limit - len(accessible))
            if remaining > 0 and accessible_collection_ids:
                coll_tuple = tuple(accessible_collection_ids)
                if coll_tuple:
                    owned_subq = select(Document.id).where(*owned_conditions)
                    shared_result = await database_session.execute(
                        select(DocumentInDocumentCollection.document_id)
                        .where(
                            DocumentInDocumentCollection.deleted_at.is_(None),
                            DocumentInDocumentCollection.document_collection_id.in_(coll_tuple),
                            ~DocumentInDocumentCollection.document_id.in_(owned_subq),
                        )
                        .distinct()
                        .order_by(DocumentInDocumentCollection.document_id)
                        .limit(remaining)
                    )
                    accessible.update(row[0] for row in shared_result)

            return sorted(accessible)[:limit]

        except SQLAlchemyError as e:
            logger.exception(
                "Database error while listing all accessible document IDs.",
                extra={"user_id": user_id, "limit": limit},
            )
            raise DatabaseException(
                "Failed to list all accessible document IDs."
            ) from e
