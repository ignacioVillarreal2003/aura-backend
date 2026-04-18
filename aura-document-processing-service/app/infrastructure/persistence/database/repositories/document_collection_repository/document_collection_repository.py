import logging
from typing import Optional
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import DocumentInDocumentCollection, UserInDocumentCollection
from app.domain.models.document import Document
from app.infrastructure.persistence.database.repositories.document_collection_repository.interfaces.document_collection_repository_interface import (
    DocumentCollectionRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import DatabaseException

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
            conditions = [Document.created_by == user_id]
            if chat_id is not None:
                conditions.append(Document.chat_id == chat_id)

            simple_result = await database_session.execute(
                select(Document.id).where(
                    Document.id.in_(document_ids),
                    Document.deleted_at.is_(None),
                    or_(*conditions)
                )
            )
            accessible: set[int] = {row[0] for row in simple_result}

            remaining = [did for did in document_ids if did not in accessible]
            if remaining:
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
                        DocumentInDocumentCollection.document_id.in_(remaining),
                        DocumentInDocumentCollection.deleted_at.is_(None)
                    )
                )
                accessible.update({row[0] for row in collection_result})

            logger.debug(
                "Accessible document IDs resolved.",
                extra={
                    "user_id": user_id,
                    "requested": len(document_ids),
                    "accessible": len(accessible)
                }
            )
            return accessible

        except Exception as e:
            raise DatabaseException("Failed to resolve accessible document IDs.") from e
