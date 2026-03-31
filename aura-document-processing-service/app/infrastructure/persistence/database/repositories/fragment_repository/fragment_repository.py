import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.fragment import Fragment
from app.infrastructure.persistence.database.repositories.exceptions.database_exceptions import (
    DatabaseConstraintViolationException,
    DatabaseException
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class FragmentRepository(FragmentRepositoryInterface):
    async def get_most_similar_fragments(
            self,
            query_vector: List[float],
            database_session: AsyncSession,
            k: int = 3,
            threshold: float = 0.3
    ) -> List[Fragment]:
        if not query_vector:
            raise DatabaseException("Invalid search vector: cannot be empty")

        if not (0.0 <= threshold <= 1.0):
            raise DatabaseException(
                f"Invalid threshold {threshold}: must be between 0.0 and 1.0"
            )

        if k < 1:
            raise DatabaseException(f"Invalid k {k}: must be at least 1")

        try:
            logger.debug(
                "Executing vector search", extra={"k": k, "threshold": threshold}
            )

            query_vector_str = "[" + ",".join(str(float(v)) for v in query_vector) + "]"

            sql = text(
                """
                SELECT id,
                       document_id,
                       content,
                       vector,
                       fragment_index,
                       summary,
                       entities,
                       topics,
                       created_by,
                       created_at,
                       updated_by,
                       updated_at,
                       deleted_by,
                       deleted_at,
                       1 - (vector <=> :query_vector) AS cosine_similarity
                FROM fragment
                WHERE vector IS NOT NULL
                  AND deleted_at IS NULL
                  AND 1 - (vector <=> :query_vector) >= :threshold
                ORDER BY cosine_similarity DESC LIMIT :k
                """
            )

            result = await database_session.execute(
                sql,
                {
                    "query_vector": query_vector_str,
                    "threshold": threshold,
                    "k": k
                }
            )
            rows = result.fetchall()

            fragments = [
                Fragment(
                    id=row.id,
                    document_id=row.document_id,
                    content=row.content,
                    vector=row.vector,
                    fragment_index=row.fragment_index,
                    summary=row.summary,
                    entities=row.entities,
                    topics=row.topics,
                    created_by=row.created_by,
                    created_at=row.created_at,
                    updated_by=row.updated_by,
                    updated_at=row.updated_at,
                    deleted_by=row.deleted_by,
                    deleted_at=row.deleted_at
                )
                for row in rows
            ]

            logger.info(
                "Vector search completed",
                extra={"k": k, "threshold": threshold, "results": len(fragments)}
            )
            return fragments

        except DatabaseException:
            raise
        except ValueError as e:
            raise DatabaseException("Invalid search vector") from e
        except Exception as e:
            raise DatabaseException("Error running vector search in pgvector") from e

    async def get_fragments_by_document_ids(
            self,
            document_ids: List[int],
            database_session: AsyncSession
    ) -> List[Fragment]:
        try:
            logger.debug(
                "Fetching fragments by document IDs",
                extra={"document_ids_count": len(document_ids)}
            )
            result = await database_session.execute(
                select(Fragment)
                .where(
                    Fragment.document_id.in_(document_ids),
                    Fragment.deleted_at.is_(None)
                )
                .order_by(Fragment.document_id, Fragment.fragment_index)
            )
            fragments = list(result.scalars().all())
            logger.debug(
                "Fragments by documents lookup completed",
                extra={"document_ids_count": len(document_ids), "count": len(fragments)}
            )
            return fragments
        except Exception as e:
            raise DatabaseException("Error fetching fragments by document IDs") from e

    async def count_fragments_missing_metadata(
            self,
            database_session: AsyncSession
    ) -> int:
        try:
            result = await database_session.execute(
                select(func.count(Fragment.id)).where(
                    Fragment.deleted_at.is_(None),
                    or_(
                        Fragment.summary.is_(None),
                        Fragment.entities.is_(None),
                        Fragment.topics.is_(None)
                    )
                )
            )
            return int(result.scalar_one())
        except Exception as e:
            raise DatabaseException(
                "Error counting fragments missing metadata from the database"
            ) from e

    async def count_fragments_missing_metadata_by_document_ids(
            self,
            document_ids: List[int],
            database_session: AsyncSession
    ) -> int:
        try:
            result = await database_session.execute(
                select(func.count(Fragment.id)).where(
                    Fragment.deleted_at.is_(None),
                    Fragment.document_id.in_(document_ids),
                    or_(
                        Fragment.summary.is_(None),
                        Fragment.entities.is_(None),
                        Fragment.topics.is_(None)
                    )
                )
            )
            return int(result.scalar_one())
        except Exception as e:
            raise DatabaseException(
                "Error counting fragments missing metadata by document IDs"
            ) from e

    async def get_fragment_ids_missing_metadata(
            self,
            database_session: AsyncSession,
            limit: int,
            last_fragment_id: Optional[int] = None
    ) -> List[int]:
        try:
            conditions = [
                Fragment.deleted_at.is_(None),
                or_(
                    Fragment.summary.is_(None),
                    Fragment.entities.is_(None),
                    Fragment.topics.is_(None)
                )
            ]
            if last_fragment_id is not None:
                conditions.append(Fragment.id > last_fragment_id)

            result = await database_session.execute(
                select(Fragment.id)
                .where(*conditions)
                .order_by(Fragment.id)
                .limit(limit)
            )
            return [int(row[0]) for row in result.fetchall()]
        except Exception as e:
            raise DatabaseException(
                "Error fetching paginated fragment IDs missing metadata from the database"
            ) from e

    async def get_fragment_ids_missing_metadata_by_document_ids(
            self,
            document_ids: List[int],
            database_session: AsyncSession,
            limit: int,
            last_fragment_id: Optional[int] = None
    ) -> List[int]:
        try:
            conditions = [
                Fragment.deleted_at.is_(None),
                Fragment.document_id.in_(document_ids),
                or_(
                    Fragment.summary.is_(None),
                    Fragment.entities.is_(None),
                    Fragment.topics.is_(None)
                )
            ]
            if last_fragment_id is not None:
                conditions.append(Fragment.id > last_fragment_id)

            result = await database_session.execute(
                select(Fragment.id)
                .where(*conditions)
                .order_by(Fragment.id)
                .limit(limit)
            )
            return [int(row[0]) for row in result.fetchall()]
        except Exception as e:
            raise DatabaseException(
                "Error fetching paginated fragment IDs missing metadata by document IDs"
            ) from e

    async def update_fragment(
            self,
            fragment: Fragment,
            database_session: AsyncSession
    ) -> Fragment:
        try:
            logger.debug("Updating fragment", extra={"fragment_id": fragment.id})

            updated_fragment = await database_session.merge(fragment)
            await database_session.flush()
            await database_session.refresh(updated_fragment)

            logger.info(
                "Fragment updated successfully",
                extra={"fragment_id": updated_fragment.id}
            )
            return updated_fragment

        except IntegrityError as e:
            raise DatabaseConstraintViolationException(
                "Constraint violation updating fragment"
            ) from e
        except Exception as e:
            raise DatabaseException("Error updating fragment in the database") from e

    async def get_fragments_by_document_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> List[Fragment]:
        try:
            logger.debug(
                "Fetching fragments by document ID", extra={"document_id": document_id}
            )

            result = await database_session.execute(
                select(Fragment)
                .where(
                    Fragment.document_id == document_id,
                    Fragment.deleted_at.is_(None)
                )
                .order_by(Fragment.fragment_index)
            )
            fragments = list(result.scalars().all())

            logger.debug(
                "Fragments fetched successfully",
                extra={"document_id": document_id, "count": len(fragments)}
            )
            return fragments

        except Exception as e:
            raise DatabaseException("Error fetching fragments by document ID") from e






    async def create_fragments(
            self,
            fragments: List[Fragment],
            database_session: AsyncSession
    ) -> List[Fragment]:
        if not fragments:
            return []

        try:
            logger.debug("Creating fragments in database", extra={"count": len(fragments)})

            database_session.add_all(fragments)
            await database_session.flush()

            for fragment in fragments:
                await database_session.refresh(fragment)

            logger.info("Fragments created successfully", extra={"count": len(fragments)})
            return fragments

        except IntegrityError as e:
            raise DatabaseConstraintViolationException(
                "Constraint violation creating fragments"
            ) from e
        except Exception as e:
            raise DatabaseException("Error creating fragments in the database") from e

    async def hard_delete_fragments_by_document_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> int:
        try:
            logger.debug(
                "Hard-deleting fragments by document ID",
                extra={"document_id": document_id}
            )

            result = await database_session.execute(
                delete(Fragment).where(Fragment.document_id == document_id)
            )
            deleted_count: int = result.rowcount
            await database_session.flush()

            logger.info(
                "Fragments hard-deleted successfully",
                extra={"document_id": document_id, "deleted_count": deleted_count}
            )
            return deleted_count

        except Exception as e:
            raise DatabaseException("Error deleting fragments from the database") from e

    async def soft_delete_fragments_by_document_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> int:
        try:
            logger.debug(
                "Soft-deleting fragments by document ID",
                extra={"document_id": document_id, "user_id": user_id}
            )

            now = datetime.now(timezone.utc)

            result = await database_session.execute(
                update(Fragment)
                .where(
                    Fragment.document_id == document_id,
                    Fragment.deleted_at.is_(None),
                )
                .values(deleted_by=user_id, deleted_at=now)
            )
            updated_count: int = result.rowcount
            await database_session.flush()

            logger.info(
                "Fragments soft-deleted successfully",
                extra={
                    "document_id": document_id,
                    "user_id": user_id,
                    "updated_count": updated_count
                }
            )
            return updated_count

        except Exception as e:
            raise DatabaseException("Error soft-deleting fragments from the database") from e
