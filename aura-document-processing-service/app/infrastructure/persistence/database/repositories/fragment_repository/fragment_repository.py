import logging
import re
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.domain.field_limits import MAX_FRAGMENTS_IN_LIST
from app.domain.dtos.document.document_search.document_similarity_hit import DocumentSimilarityHit
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
    async def get_fragment_by_id(
            self,
            fragment_id: int,
            database_session: AsyncSession,
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
            database_session: AsyncSession,
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
                .options(
                    load_only(
                        Fragment.id,
                        Fragment.document_id,
                        Fragment.content,
                        Fragment.fragment_index,
                    )
                )
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
            threshold: float = 0.3,
            document_ids: List[int] | None = None,
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
                    "threshold": threshold,
                    "doc_filter": len(document_ids) if document_ids else "none",
                }
            )

            query_vector_str = "[" + ",".join(str(float(v)) for v in query_vector) + "]"

            doc_id_filter = ""
            if document_ids:
                ids_literal = ",".join(str(int(d)) for d in document_ids)
                doc_id_filter = f"AND document_id IN ({ids_literal})"

            sql = text(
                f"""
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
                  {doc_id_filter}
                ORDER BY cosine_similarity DESC
                LIMIT :k
                """
            )

            result = await database_session.execute(
                sql,
                {
                    "query_vector": query_vector_str,
                    "threshold": threshold,
                    "k": k,
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

    async def search_documents_by_similarity(
            self,
            query_vector: List[float],
            database_session: AsyncSession,
            k: int,
            threshold: float,
            pool_size: int,
            document_ids: List[int] | None = None,
    ) -> List[DocumentSimilarityHit]:
        if not query_vector:
            raise DatabaseException("The search vector cannot be empty.")

        if not (0.0 <= threshold <= 1.0):
            raise DatabaseException(
                "The similarity threshold must be between 0.0 and 1.0."
            )

        if k < 1:
            raise DatabaseException("The result count k must be at least 1.")

        if pool_size < k:
            raise DatabaseException("The candidate pool size must be at least k.")

        try:
            logger.debug(
                "Executing document-level vector similarity search.",
                extra={
                    "k": k,
                    "threshold": threshold,
                    "pool_size": pool_size,
                    "doc_filter": len(document_ids) if document_ids else "none",
                }
            )

            query_vector_str = "[" + ",".join(str(float(v)) for v in query_vector) + "]"

            doc_id_filter = ""
            if document_ids:
                ids_literal = ",".join(str(int(d)) for d in document_ids)
                doc_id_filter = f"AND document_id IN ({ids_literal})"

            sql = text(
                f"""
                SELECT document_id,
                       MAX(cosine_similarity)                                  AS best_similarity,
                       COUNT(*)                                                AS matched_fragments,
                       (ARRAY_AGG(content ORDER BY cosine_similarity DESC))[1] AS best_fragment_content
                FROM (
                    SELECT document_id,
                           content,
                           1 - (vector <=> :query_vector) AS cosine_similarity
                    FROM fragment
                    WHERE vector IS NOT NULL
                      AND deleted_at IS NULL
                      AND 1 - (vector <=> :query_vector) >= :threshold
                      {doc_id_filter}
                    ORDER BY cosine_similarity DESC
                    LIMIT :pool_size
                ) AS top_fragments
                GROUP BY document_id
                ORDER BY best_similarity DESC
                LIMIT :k
                """
            )

            result = await database_session.execute(
                sql,
                {
                    "query_vector": query_vector_str,
                    "threshold": threshold,
                    "pool_size": pool_size,
                    "k": k,
                }
            )
            rows = result.fetchall()

            hits = [
                DocumentSimilarityHit(
                    document_id=row.document_id,
                    best_similarity=min(max(float(row.best_similarity), 0.0), 1.0),
                    matched_fragments=int(row.matched_fragments),
                    best_fragment_content=row.best_fragment_content,
                )
                for row in rows
            ]

            logger.debug(
                "The document-level vector similarity search completed.",
                extra={
                    "k": k,
                    "threshold": threshold,
                    "results": len(hits)
                }
            )
            return hits

        except DatabaseException:
            raise
        except ValueError as e:
            raise DatabaseException("The search vector is invalid.") from e
        except SQLAlchemyError as e:
            logger.exception(
                "Database error during document-level vector similarity search.",
                extra={"k": k, "threshold": threshold},
            )
            raise DatabaseException("Failed to run document-level vector similarity search.") from e

    async def get_most_relevant_fragments_bm25(
            self,
            *,
            query: str,
            database_session: AsyncSession,
            k: int,
            min_score: float = 0.0,
            query_max_chars: int = 512,
            document_ids: list[int] | None = None,
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
            doc_id_filter = ""
            if document_ids:
                ids_literal = ",".join(str(int(d)) for d in document_ids)
                doc_id_filter = f"AND document_id IN ({ids_literal})"

            sql = text(
                f"""
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
                  {doc_id_filter}
                  AND paradedb.score(id) >= :min_score
                ORDER BY paradedb.score(id) DESC
                LIMIT :k
                """
            )
            result = await database_session.execute(
                sql,
                {
                    "search_query": sanitized,
                    "min_score": float(min_score),
                    "k": int(k),
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
            database_session: AsyncSession,
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

    async def get_adjacent_fragments(
            self,
            fragments: List[Fragment],
            window: int,
            database_session: AsyncSession,
            exclude_ids: set[int],
    ) -> List[Fragment]:
        if not fragments or window <= 0:
            return []

        try:
            conditions = [
                and_(
                    Fragment.document_id == f.document_id,
                    Fragment.fragment_index.between(
                        max(0, int(f.fragment_index) - window),
                        int(f.fragment_index) + window,
                    ),
                )
                for f in fragments
            ]

            stmt = (
                select(Fragment)
                .where(
                    Fragment.deleted_at.is_(None),
                    Fragment.id.not_in(exclude_ids) if exclude_ids else True,
                    or_(*conditions),
                )
                .order_by(Fragment.document_id, Fragment.fragment_index)
                .limit(MAX_FRAGMENTS_IN_LIST)
            )

            result = await database_session.execute(stmt)
            adjacent = list(result.scalars().all())

            logger.debug(
                "Adjacent fragments retrieved.",
                extra={"window": window, "count": len(adjacent)},
            )
            return adjacent

        except SQLAlchemyError as e:
            logger.exception("Database error while fetching adjacent fragments.")
            raise DatabaseException("Failed to fetch adjacent fragments.") from e

    async def create_fragments(
            self,
            fragments: List[Fragment],
            database_session: AsyncSession,
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
            database_session: AsyncSession,
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
            database_session: AsyncSession,
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
