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
from app.domain.dtos.document.document_query.document_response import DocumentResponse
from app.domain.dtos.document.document_search.document_search_request import DocumentSearchRequest
from app.domain.dtos.document.document_search.document_search_response import (
    DocumentSearchListResponse,
    DocumentSearchResultResponse,
)
from app.domain.dtos.document.document_search.document_similarity_hit import DocumentSimilarityHit
from app.domain.field_limits import MAX_DOCUMENT_SEARCH_SNIPPET_CHARS
from app.infrastructure.http.document_collection_catalog.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)


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
        logger.info(
            "Searching documents by content was initiated.",
            extra={
                "query_length": len(document_search_request.query),
                "max_documents": document_search_request.max_documents,
                "user_id": authenticated_user.id,
            },
        )

        try:
            accessible_doc_set: set[int] = set(
                await self._document_collection_catalog_client.fetch_all_accessible_document_ids(
                    user_id=int(authenticated_user.id),
                    authorization_header=authorization_header,
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
                return DocumentSearchListResponse(results=[])

            query_vector = await self._get_query_embedding(text=document_search_request.query)

            hits = await self._retrieve_document_hits(
                query_vector=query_vector,
                database_session=database_session,
                k=document_search_request.max_documents,
                document_ids=list(accessible_doc_set),
            )
            hits = [hit for hit in hits if hit.document_id in accessible_doc_set]

            results = await self._build_search_results(
                hits=hits,
                database_session=database_session,
            )

            logger.info(
                "Documents were searched by content successfully.",
                extra={
                    "user_id": authenticated_user.id,
                    "result_count": len(results),
                },
            )
            return DocumentSearchListResponse(results=results)

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

    async def _get_query_embedding(self, text: str) -> list[float]:
        try:
            vector: list[float] = await self._embedder_factory.embedder.aembed_query(text=text)
            logger.debug("Search query embedding generated.", extra={"text_length": len(text)})
            return vector
        except Exception as e:
            raise DocumentSearchEmbeddingException("Failed to generate the search query embedding.") from e

    async def _retrieve_document_hits(
            self,
            query_vector: list[float],
            database_session: AsyncSession,
            k: int,
            document_ids: list[int],
    ) -> list[DocumentSimilarityHit]:
        try:
            hits = await self._fragment_repository.search_documents_by_similarity(
                query_vector=query_vector,
                database_session=database_session,
                k=k,
                threshold=self._settings.similarity_threshold,
                pool_size=max(self._settings.candidate_pool_size, k),
                embedding_identity=self._embedder_factory.get_active_embedding_identity(),
                document_ids=document_ids,
            )
            logger.debug("Document similarity hits retrieved.", extra={"hit_count": len(hits)})
            return hits
        except Exception as e:
            raise DocumentSearchRetrievalException("Failed to retrieve similar documents.") from e

    async def _build_search_results(
            self,
            hits: list[DocumentSimilarityHit],
            database_session: AsyncSession,
    ) -> list[DocumentSearchResultResponse]:
        if not hits:
            return []

        documents = await self._document_repository.get_documents_by_ids(
            document_ids=[hit.document_id for hit in hits],
            database_session=database_session,
        )
        docs_by_id = {int(doc.id): doc for doc in documents}

        results: list[DocumentSearchResultResponse] = []
        for hit in hits:
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
                    similarity=hit.best_similarity,
                    matched_fragments=hit.matched_fragments,
                    best_fragment_snippet=self._build_snippet(hit.best_fragment_content),
                )
            )
        return results

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
