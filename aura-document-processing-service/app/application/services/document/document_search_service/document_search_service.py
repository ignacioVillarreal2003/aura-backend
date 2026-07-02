import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.services.document.document_search_service.document_search_service_settings import (
    DocumentSearchServiceSettings,
)
from app.application.services.document.document_search_service.exceptions.document_search_service_exception import (
    DocumentSearchEmbeddingException,
    DocumentSearchInvalidRequestException,
    DocumentSearchRetrievalException,
    DocumentSearchServiceException,
)
from app.application.services.document.document_search_service.interfaces.document_search_service_interface import (
    DocumentSearchServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.document.document_search_mode import DocumentSearchMode
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.dtos.document.document_search.document_search_request import DocumentSearchRequest
from app.domain.dtos.document.document_search.document_search_response import (
    DocumentSearchListResponse,
    DocumentSearchResultResponse,
)
from app.domain.dtos.document.document_search.document_similarity_hit import DocumentSimilarityHit
from app.domain.field_limits import (
    MAX_DOCUMENT_SEARCH_CANDIDATE_POOL,
    MAX_DOCUMENT_SEARCH_SNIPPET_CHARS,
)
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.http.document_collection_catalog.interfaces.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)

_ScoredHit = tuple[DocumentSimilarityHit, float, float]


class DocumentSearchService(DocumentSearchServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            embedder_factory: EmbedderFactory,
            document_collection_catalog_client: DocumentCollectionCatalogClientInterface,
            document_search_service_settings: Optional[DocumentSearchServiceSettings] = None,
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._embedder_factory = embedder_factory
        self._document_collection_catalog_client = document_collection_catalog_client
        self._settings = document_search_service_settings or DocumentSearchServiceSettings()

    async def search_documents_by_content(
            self,
            document_search_request: DocumentSearchRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
            authorization_header: Optional[str] = None,
    ) -> DocumentSearchListResponse:
        mode = document_search_request.mode
        page = document_search_request.page
        page_size = document_search_request.page_size
        offset = document_search_request.offset

        logger.info(
            "Searching documents by content was initiated.",
            extra={
                "query_length": len(document_search_request.query),
                "mode": mode.value,
                "page": page,
                "page_size": page_size,
                "user_id": authenticated_user.id,
            },
        )

        empty_response = DocumentSearchListResponse(
            results=[], mode=mode, page=page, page_size=page_size, has_more=False
        )

        try:
            token = authorization_header or get_request_token()
            accessible_doc_set: set[int] = set(
                await self._document_collection_catalog_client.fetch_all_accessible_document_ids(
                    user_id=int(authenticated_user.id),
                    authorization_header=token,
                )
            )
            logger.debug(
                "Accessible document IDs resolved for the content search.",
                extra={
                    "user_id": authenticated_user.id,
                    "accessible_doc_count": len(accessible_doc_set),
                },
            )

            if not accessible_doc_set:
                logger.info(
                    "The user has no accessible documents; returning an empty search result.",
                    extra={"user_id": authenticated_user.id},
                )
                return empty_response

            accessible_ids = list(accessible_doc_set)

            scored_hits, has_more = await self._search_paginated(
                mode=mode,
                query=document_search_request.query,
                database_session=database_session,
                page_size=page_size,
                offset=offset,
                document_ids=accessible_ids,
                accessible_doc_set=accessible_doc_set,
            )

            results = await self._build_search_results(
                scored_hits=scored_hits,
                database_session=database_session,
            )

            logger.info(
                "Documents were searched by content successfully.",
                extra={
                    "user_id": authenticated_user.id,
                    "mode": mode.value,
                    "page": page,
                    "result_count": len(results),
                    "has_more": has_more,
                },
            )
            return DocumentSearchListResponse(
                results=results,
                mode=mode,
                page=page,
                page_size=page_size,
                has_more=has_more,
            )

        except (
                DocumentSearchInvalidRequestException,
                DocumentSearchEmbeddingException,
                DocumentSearchRetrievalException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while searching documents by content.",
                extra={"user_id": authenticated_user.id},
            )
            raise DocumentSearchServiceException(
                "An unexpected error occurred while searching documents by content."
            ) from e

    async def _search_paginated(
            self,
            *,
            mode: DocumentSearchMode,
            query: str,
            database_session: AsyncSession,
            page_size: int,
            offset: int,
            document_ids: list[int],
            accessible_doc_set: set[int],
    ) -> tuple[list[_ScoredHit], bool]:
        if offset >= MAX_DOCUMENT_SEARCH_CANDIDATE_POOL:
            return [], False

        fetch_limit = page_size + 1
        pool_size = min(
            max(self._settings.candidate_pool_size, offset + fetch_limit),
            MAX_DOCUMENT_SEARCH_CANDIDATE_POOL,
        )
        if pool_size < offset + fetch_limit:
            fetch_limit = pool_size - offset
        if fetch_limit < 1:
            return [], False

        if mode is DocumentSearchMode.bm25:
            hits = await self._retrieve_bm25_hits(
                query=query,
                database_session=database_session,
                k=fetch_limit,
                offset=offset,
                pool_size=pool_size,
                document_ids=document_ids,
            )
        else:
            hits = await self._retrieve_vector_hits(
                query=query,
                database_session=database_session,
                k=fetch_limit,
                offset=offset,
                pool_size=pool_size,
                document_ids=document_ids,
            )

        hits = [hit for hit in hits if hit.document_id in accessible_doc_set]
        has_more = len(hits) > page_size
        page_hits = hits[:page_size]
        scored = [(hit, self._normalize_similarity(mode, hit.score), hit.score) for hit in page_hits]
        return scored, has_more

    async def _retrieve_vector_hits(
            self,
            *,
            query: str,
            database_session: AsyncSession,
            k: int,
            offset: int,
            pool_size: int,
            document_ids: list[int],
    ) -> list[DocumentSimilarityHit]:
        query_vector = await self._get_query_embedding(text=query)
        try:
            hits = await self._fragment_repository.search_documents_by_similarity(
                query_vector=query_vector,
                database_session=database_session,
                k=k,
                threshold=self._settings.similarity_threshold,
                pool_size=pool_size,
                embedding_identity=self._embedder_factory.get_active_embedding_identity(),
                offset=offset,
                document_ids=document_ids,
            )
            logger.debug("Vector document hits retrieved.", extra={"hit_count": len(hits)})
            return hits
        except Exception as e:
            raise DocumentSearchRetrievalException("Failed to retrieve similar documents.") from e

    async def _retrieve_bm25_hits(
            self,
            *,
            query: str,
            database_session: AsyncSession,
            k: int,
            offset: int,
            pool_size: int,
            document_ids: list[int],
    ) -> list[DocumentSimilarityHit]:
        try:
            hits = await self._fragment_repository.search_documents_by_bm25(
                query=query,
                database_session=database_session,
                k=k,
                pool_size=pool_size,
                offset=offset,
                min_score=self._settings.bm25_min_score,
                query_max_chars=self._settings.bm25_query_max_chars,
                document_ids=document_ids,
            )
            logger.debug("BM25 document hits retrieved.", extra={"hit_count": len(hits)})
            return hits
        except Exception as e:
            raise DocumentSearchRetrievalException("Failed to retrieve relevant documents.") from e

    async def _get_query_embedding(self, text: str) -> list[float]:
        try:
            vector: list[float] = await self._embedder_factory.embedder.aembed_query(text=text)
            logger.debug("Search query embedding generated.", extra={"text_length": len(text)})
            return vector
        except Exception as e:
            raise DocumentSearchEmbeddingException("Failed to generate the search query embedding.") from e

    async def _build_search_results(
            self,
            scored_hits: list[_ScoredHit],
            database_session: AsyncSession,
    ) -> list[DocumentSearchResultResponse]:
        if not scored_hits:
            return []

        documents = await self._document_repository.get_documents_by_ids(
            document_ids=[hit.document_id for hit, _, _ in scored_hits],
            database_session=database_session,
        )
        docs_by_id = {int(doc.id): doc for doc in documents}

        results: list[DocumentSearchResultResponse] = []
        for hit, similarity, score in scored_hits:
            doc = docs_by_id.get(hit.document_id)
            if doc is None:
                logger.warning(
                    "Document not found for similarity hit; skipping.",
                    extra={"document_id": hit.document_id},
                )
                continue
            results.append(
                DocumentSearchResultResponse(
                    document=DocumentResponse.model_validate(doc),
                    similarity=similarity,
                    score=score,
                    matched_fragments=hit.matched_fragments,
                    best_fragment_snippet=self._build_snippet(hit.best_fragment_content),
                )
            )
        return results

    def _normalize_similarity(self, mode: DocumentSearchMode, score: float) -> float:
        if mode is DocumentSearchMode.bm25:
            saturation = self._settings.bm25_relevance_saturation
            value = score / (score + saturation)
        else:
            value = score
        return min(max(value, 0.0), 1.0)

    @staticmethod
    def _build_snippet(content: Optional[str]) -> Optional[str]:
        if content is None:
            return None
        normalized = " ".join(content.split())
        if not normalized:
            return None
        if len(normalized) <= MAX_DOCUMENT_SEARCH_SNIPPET_CHARS:
            return normalized
        return normalized[: MAX_DOCUMENT_SEARCH_SNIPPET_CHARS - 1].rstrip() + "…"
