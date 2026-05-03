import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.field_limits import MAX_FRAGMENTS_IN_LIST

from app.infrastructure.persistence.database.orm.fragment import Fragment
from app.infrastructure.persistence.database.repositories.database_exceptions import (
    DatabaseConstraintViolationException,
    DatabaseException,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_interface import (
    FragmentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.repository_query_utils import chunked_ids

logger = logging.getLogger(__name__)


def _sanitize_bm25_search_input(raw: str, max_chars: int) -> str:
    printable_only = "".join(c for c in raw if c.isprintable())
    allowed = re.sub(r"[^\w\s\-.,]", " ", printable_only, flags=re.UNICODE)
    collapsed = re.sub(r"\s+", " ", allowed).strip()
    if not collapsed:
        return ""
    return collapsed[:max_chars] if len(collapsed) > max_chars else collapsed


class FragmentRepository(FragmentRepositoryInterface):
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
        except SQLAlchemyError as e:
            logger.exception("Database error while counting fragments missing metadata.")
            raise DatabaseException("Failed to count fragments missing metadata.") from e

    async def count_fragments_missing_metadata_by_document_ids(
            self,
            document_ids: List[int],
            database_session: AsyncSession
    ) -> int:
        if not document_ids:
            return 0
        try:
            total = 0
            for chunk in chunked_ids(document_ids):
                result = await database_session.execute(
                    select(func.count(Fragment.id)).where(
                        Fragment.deleted_at.is_(None),
                        Fragment.document_id.in_(chunk),
                        or_(
                            Fragment.summary.is_(None),
                            Fragment.entities.is_(None),
                            Fragment.topics.is_(None)
                        )
                    )
                )
                total += int(result.scalar_one())
            return total
        except SQLAlchemyError as e:
            logger.exception(
                "Database error while counting fragments missing metadata for document IDs.",
                extra={"document_ids_count": len(document_ids)},
            )
            raise DatabaseException(
                "Failed to count fragments missing metadata for the given document IDs."
            ) from e

    async def get_fragment_by_id(
            self,
            fragment_id: int,
            database_session: AsyncSession
    ) -> Optional[Fragment]:
        try:
            result = await database_session.execute(
                select(Fragment).where(
                    Fragment.id == fragment_id,
                    Fragment.deleted_at.is_(None),
                )
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            logger.exception(
                "Database error while fetching fragment by ID.",
                extra={"fragment_id": fragment_id},
            )
            raise DatabaseException("Failed to fetch the fragment.") from e

    async def get_fragments_by_document_id(
            self,
            document_id: int,
            database_session: AsyncSession
    ) -> List[Fragment]:
        try:
            logger.debug(
                "Fetching fragments by document ID.",
                extra={
                    "document_id": document_id
                }
            )

            result = await database_session.execute(
                select(Fragment)
                .where(
                    Fragment.document_id == document_id,
                    Fragment.deleted_at.is_(None)
                )
                .order_by(Fragment.fragment_index)
                .limit(MAX_FRAGMENTS_IN_LIST)
            )
            fragments = list(result.scalars().all())

            logger.debug(
                "The fragments were fetched successfully.",
                extra={
                    "document_id": document_id,
                    "count": len(fragments)
                }
            )
            return fragments

        except SQLAlchemyError as e:
            logger.exception(
                "Database error while fetching fragments by document ID.",
                extra={"document_id": document_id},
            )
            raise DatabaseException("Failed to fetch fragments by document ID.") from e

    async def get_most_similar_fragments(
            self,
            query_vector: List[float],
            database_session: AsyncSession,
            k: int = 3,
            threshold: float = 0.3
    ) -> List[Fragment]:
        if not query_vector:
            raise DatabaseException("The search vector cannot be empty.")

        if not (0.0 <= threshold <= 1.0):
            raise DatabaseException(
                "The similarity threshold must be between 0.0 and 1.0."
            )

        if k < 1:
            raise DatabaseException("The result count k must be at least 1.")

        try:
            logger.debug(
                "Executing vector similarity search.",
                extra={
                    "k": k,
                    "threshold": threshold
                }
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
                ORDER BY cosine_similarity DESC
                LIMIT :k
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

            logger.debug(
                "The vector similarity search completed.",
                extra={
                    "k": k,
                    "threshold": threshold,
                    "results": len(fragments)
                }
            )
            return fragments

        except DatabaseException:
            raise
        except ValueError as e:
            raise DatabaseException("The search vector is invalid.") from e
        except SQLAlchemyError as e:
            logger.exception(
                "Database error during vector similarity search.",
                extra={"k": k, "threshold": threshold},
            )
            raise DatabaseException("Failed to run vector similarity search.") from e

    async def get_most_relevant_fragments_bm25(
            self,
            *,
            query: str,
            database_session: AsyncSession,
            k: int,
            min_score: float = 0.0,
            query_max_chars: int = 512,
    ) -> List[Fragment]:
        sanitized = _sanitize_bm25_search_input(query, query_max_chars)
        if not sanitized:
            logger.debug(
                "BM25 search skipped: query empty after sanitization.",
                extra={"query_max_chars": query_max_chars},
            )
            return []

        if k < 1:
            raise DatabaseException("The BM25 result count k must be at least 1.")

        try:
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
                       deleted_at
                FROM fragment
                WHERE deleted_at IS NULL
                  AND content @@@ :search_query
                  AND paradedb.score(id) >= :min_score
                ORDER BY paradedb.score(id) DESC
                LIMIT :k
                """
            )
            result = await database_session.execute(
                sql,
                {
                    "search_query": sanitized,
                    "min_score": min_score,
                    "k": k,
                },
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
                    deleted_at=row.deleted_at,
                )
                for row in rows
            ]
            logger.debug(
                "BM25 fragment retrieval completed.",
                extra={"k": k, "results": len(fragments)},
            )
            return fragments

        except SQLAlchemyError as e:
            logger.exception(
                "Database error during BM25 fragment search.",
                extra={"k": k},
            )
            raise DatabaseException("Failed to run BM25 similarity search.") from e

    async def get_fragments_by_document_ids(
            self,
            document_ids: List[int],
            database_session: AsyncSession
    ) -> List[Fragment]:
        if not document_ids:
            return []
        try:
            logger.debug(
                "Fetching fragments by document IDs.",
                extra={
                    "document_ids_count": len(document_ids)
                }
            )
            fragments: list[Fragment] = []
            for chunk in chunked_ids(document_ids):
                result = await database_session.execute(
                    select(Fragment)
                    .where(
                        Fragment.document_id.in_(chunk),
                        Fragment.deleted_at.is_(None)
                    )
                    .order_by(Fragment.document_id, Fragment.fragment_index)
                )
                fragments.extend(list(result.scalars().all()))

            fragments.sort(key=lambda f: (int(f.document_id), int(f.fragment_index)))

            logger.debug(
                "The fragments-by-documents lookup completed.",
                extra={
                    "document_ids_count": len(document_ids),
                    "count": len(fragments)
                }
            )
            return fragments
        except SQLAlchemyError as e:
            logger.exception(
                "Database error while fetching fragments by document IDs.",
                extra={"document_ids_count": len(document_ids)},
            )
            raise DatabaseException("Failed to fetch fragments by document IDs.") from e

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
        except SQLAlchemyError as e:
            logger.exception("Database error while fetching fragment IDs missing metadata.")
            raise DatabaseException("Failed to fetch paginated fragment IDs missing metadata.") from e

    async def get_fragment_ids_missing_metadata_by_document_ids(
            self,
            document_ids: List[int],
            database_session: AsyncSession,
            limit: int,
            last_fragment_id: Optional[int] = None
    ) -> List[int]:
        if not document_ids:
            return []
        try:
            collected: list[int] = []
            for chunk in chunked_ids(document_ids):
                remaining = limit - len(collected)
                if remaining <= 0:
                    break
                conditions = [
                    Fragment.deleted_at.is_(None),
                    Fragment.document_id.in_(chunk),
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
                    .limit(remaining)
                )
                collected.extend(int(row[0]) for row in result.fetchall())

            collected.sort()
            return collected[:limit]
        except SQLAlchemyError as e:
            logger.exception(
                "Database error while fetching fragment IDs missing metadata for document IDs.",
                extra={"document_ids_count": len(document_ids)},
            )
            raise DatabaseException(
                "Failed to fetch paginated fragment IDs missing metadata for the given document IDs."
            ) from e

    async def create_fragments(
            self,
            fragments: List[Fragment],
            database_session: AsyncSession
    ) -> List[Fragment]:
        if not fragments:
            return []

        try:
            logger.debug(
                "Creating fragments in the database.",
                extra={
                    "count": len(fragments)
                }
            )

            database_session.add_all(fragments)
            await database_session.flush()

            for fragment in fragments:
                await database_session.refresh(fragment)

            logger.info(
                "The fragments were created successfully.",
                extra={
                    "count": len(fragments)
                }
            )
            return fragments

        except IntegrityError as e:
            raise DatabaseConstraintViolationException(
                "A database constraint was violated while creating fragments."
            ) from e
        except SQLAlchemyError as e:
            logger.exception(
                "Failed to create fragments.",
                extra={"count": len(fragments)},
            )
            raise DatabaseException("Failed to create fragments.") from e

    async def update_fragment(
            self,
            fragment: Fragment,
            database_session: AsyncSession
    ) -> Fragment:
        try:
            logger.debug(
                "Updating the fragment.",
                extra={
                    "fragment_id": fragment.id
                }
            )

            updated_fragment = await database_session.merge(fragment)
            await database_session.flush()
            await database_session.refresh(updated_fragment)

            logger.info(
                "The fragment was updated successfully.",
                extra={
                    "fragment_id": updated_fragment.id
                }
            )
            return updated_fragment

        except IntegrityError as e:
            raise DatabaseConstraintViolationException(
                "A database constraint was violated while updating the fragment."
            ) from e
        except SQLAlchemyError as e:
            logger.exception(
                "Failed to update the fragment.",
                extra={"fragment_id": fragment.id},
            )
            raise DatabaseException("Failed to update the fragment.") from e

    async def soft_delete_fragments_by_document_id(
            self,
            document_id: int,
            user_id: int,
            database_session: AsyncSession
    ) -> int:
        try:
            logger.debug(
                "Soft-deleting fragments by document ID.",
                extra={
                    "document_id": document_id,
                    "user_id": user_id
                }
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
                "The fragments were soft-deleted successfully.",
                extra={
                    "document_id": document_id,
                    "user_id": user_id,
                    "updated_count": updated_count
                }
            )
            return updated_count

        except SQLAlchemyError as e:
            logger.exception(
                "Failed to soft-delete fragments.",
                extra={"document_id": document_id, "user_id": user_id},
            )
            raise DatabaseException("Failed to soft-delete fragments.") from e
