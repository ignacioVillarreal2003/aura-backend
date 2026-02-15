from datetime import datetime
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging

from app.domain.models.fragment import Fragment
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import DatabaseException
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class FragmentRepository(FragmentRepositoryInterface):
    async def create_fragments(
            self,
            fragments: List[Fragment],
            database_session: AsyncSession
    ) -> List[Fragment]:
        try:
            logger.debug("Creating fragments in database")

            database_session.add_all(fragments)
            await database_session.commit()

            for fragment in fragments:
                await database_session.refresh(fragment)

            logger.info("Created fragments successfully")
            return fragments

        except Exception as e:
            await database_session.rollback()
            logger.exception("Failed to create fragments in database")
            raise DatabaseException("Error creating fragments in the database") from e

    async def get_fragments_by_document_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> List[Fragment]:
        try:
            logger.debug(f"Fetching fragments by document id")

            result = await database_session.execute(
                select(Fragment).filter(
                    Fragment.document_id == document_id
                )
            )
            fragments = result.scalars().all()

            logger.debug("Fetched fragments successfully")
            return list(fragments)

        except Exception as e:
            logger.exception("Failed to fetch fragments by document id")
            raise DatabaseException("Error fetching fragments by document id") from e

    async def get_most_similar_fragments(
            self,
            query_vector: List[float],
            database_session: AsyncSession,
            k: Optional[int] = 3,
            threshold: Optional[float] = 0.3
    ) -> List[Fragment]:
        try:
            logger.debug("Executing vector search")

            query_vector_str = "[" + ",".join(str(float(x)) for x in query_vector) + "]"

            sql = text(
                """
                SELECT id,
                       document_id,
                       vector,
                       content,
                       fragment_index,
                       created_by,
                       created_at,
                       deleted_by,
                       deleted_at,
                       1 - (vector <=> :query_vector) AS cosine_similarity
                FROM fragment
                WHERE vector IS NOT NULL
                  AND 1 - (vector <=> :query_vector) >= :threshold
                ORDER BY cosine_similarity DESC LIMIT :k
                """
            )

            result = await database_session.execute(
                sql,
                {
                    "query_vector": query_vector_str,
                    "k": k,
                    "threshold": threshold
                }
            )
            rows = result.fetchall()

            logger.info("Vector search completed.")

            fragments = []
            for row in rows:
                fragments.append(Fragment(
                    id=row.id,
                    document_id=row.document_id,
                    vector=row.vector,
                    content=row.content,
                    fragment_index=row.fragment_index,
                    created_by=row.created_by,
                    created_at=row.created_at,
                    deleted_by=row.deleted_by,
                    deleted_at=row.deleted_at
                ))

            return fragments

        except ValueError as e:
            logger.error(f"Invalid query vector: {e}")
            raise DatabaseException("Invalid search vector") from e
        except Exception as e:
            logger.exception("Error during vector search")
            raise DatabaseException("Error running vector search in pgvector") from e

    async def hard_delete_fragments_by_document_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> bool:
        try:
            logger.debug("Deleting fragments by document id")

            result = await database_session.execute(
                select(Fragment).filter(
                    Fragment.document_id == document_id
                )
            )
            fragments = result.scalars().all()

            if not fragments:
                logger.warning("No fragments found")
                return False

            for fragment in fragments:
                await database_session.delete(fragment)

            await database_session.commit()
            logger.info(f"Deleted fragments successfully")
            return True

        except Exception as e:
            await database_session.rollback()
            logger.exception("Failed to delete fragments from database")
            raise DatabaseException("Error deleting fragments from the database") from e

    async def soft_delete_fragments_by_document_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> bool:
        try:
            logger.debug("Soft deleting fragments by document id")

            result = await database_session.execute(
                select(Fragment).filter(
                    Fragment.document_id == document_id
                )
            )
            fragments = result.scalars().all()

            if not fragments:
                logger.warning("No fragments found")
                return False

            for fragment in fragments:
                fragment.deleted_by = user_id
                fragment.deleted_at = datetime.now()

            await database_session.commit()

            logger.info(f"Soft deleted fragments successfully")
            return True

        except Exception as e:
            await database_session.rollback()
            logger.exception("Failed to delete fragments from database")
            raise DatabaseException("Error deleting fragments from the database") from e
