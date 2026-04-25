import logging
from typing import Optional
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.orm.document_in_document_collection import DocumentInDocumentCollection
from app.infrastructure.persistence.database.orm.user_in_document_collection import UserInDocumentCollection
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
            database_session: AsyncSession
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
                        or_(*conditions)
                    )
                )
                accessible.update(row[0] for row in simple_result)

            remaining_ordered = [did for did in dict.fromkeys(document_ids) if did not in accessible]
            if remaining_ordered:
                for chunk in chunked_ids(remaining_ordered):
                    collection_result = await database_session.execute(
                        select(DocumentInDocumentCollection.document_id).join(
                            UserInDocumentCollection,
                            and_(
                                UserInDocumentCollection.document_collection_id
                                == DocumentInDocumentCollection.document_collection_id,
                                UserInDocumentCollection.user_id == user_id,
                                UserInDocumentCollection.deleted_at.is_(None)
                            )
                        ).where(
                            DocumentInDocumentCollection.document_id.in_(chunk),
                            DocumentInDocumentCollection.deleted_at.is_(None)
                        )
                    )
                    accessible.update(row[0] for row in collection_result)

            logger.debug(
                "Accessible document IDs resolved.",
                extra={
                    "user_id": user_id,
                    "requested": len(document_ids),
                    "accessible": len(accessible)
                }
            )
            return accessible

        except SQLAlchemyError as e:
            logger.exception(
                "Database error while resolving accessible document IDs.",
                extra={"user_id": user_id, "requested_count": len(document_ids)},
            )
            raise DatabaseException("Failed to resolve accessible document IDs.") from e
