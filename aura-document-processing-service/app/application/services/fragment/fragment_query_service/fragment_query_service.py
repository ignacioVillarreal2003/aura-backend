import asyncio
import logging
from typing import Optional, Protocol, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.rerankers.reranker_factory import RerankerFactory
from app.application.services.fragment.fragment_query_service.exceptions.fragment_query_service_exception import (
    FragmentQueryEmbeddingException,
    FragmentQueryInvalidRequestException,
    FragmentQueryNotFoundException,
    FragmentQueryRetrievalException,
    FragmentQueryServiceException,
)
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.services.fragment.fragment_query_service.fragment_query_service_settings import (
    FragmentQueryServiceSettings,
)
from app.application.services.fragment.fragment_query_service.interfaces.fragment_query_service_interface import (
    FragmentQueryServiceInterface,
)
from app.domain.dtos.fragment.fragment_query.documents_context_fragments_request import (
    DocumentsContextFragmentsRequest,
)
from app.domain.dtos.fragment.fragment_query.fragment_list_response import FragmentListResponse
from app.domain.dtos.fragment.fragment_query.fragment_response import FragmentResponse
from app.domain.dtos.fragment.fragment_query.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_collection_catalog.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.orm.fragment import Fragment
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)


class _HasId(Protocol):
    id: int


_T = TypeVar("_T", bound=_HasId)


def _reciprocal_rank_fusion(*, ranked_lists: list[list[_T]], k: int = 60) -> list[_T]:
    if not ranked_lists:
        return []
    scores: dict[int, float] = {}
    by_id: dict[int, _T] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            fid = int(item.id)
            scores[fid] = scores.get(fid, 0.0) + 1.0 / (float(k) + float(rank))
            by_id.setdefault(fid, item)
    return sorted(by_id.values(), key=lambda f: scores[int(f.id)], reverse=True)


class FragmentQueryService(FragmentQueryServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            embedder_factory: EmbedderFactory,
            reranker_factory: RerankerFactory,
            document_collection_catalog_client: DocumentCollectionCatalogClientInterface,
            fragment_query_service_settings: Optional[FragmentQueryServiceSettings] = None,
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._embedder_factory = embedder_factory
        self._reranker_factory = reranker_factory
        self._settings = fragment_query_service_settings or FragmentQueryServiceSettings()
        self._document_collection_catalog_client = document_collection_catalog_client

    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
            authorization_header: str | None = None,
    ) -> FragmentListResponse:
        logger.info(
            "Retrieving context fragments by question was initiated.",
            extra={
                "semantic_query_count": len(question_context_fragments_request.semantic_queries),
                "bm25_query_count": len(question_context_fragments_request.bm25_queries),
                "rerank_enabled": question_context_fragments_request.rerank.enabled,
                "user_id": authenticated_user.id,
            },
        )

        try:
            collection_doc_ids = await self._document_collection_catalog_client.fetch_all_accessible_document_ids(
                user_id=int(authenticated_user.id),
                authorization_header=authorization_header,
            )
            logger.debug(
                "Accessible document IDs fetched from collection service.",
                extra={
                    "user_id": authenticated_user.id,
                    "collection_doc_count": len(collection_doc_ids),
                },
            )
            accessible_doc_ids = list(collection_doc_ids)
            accessible_doc_set: set[int] = set(accessible_doc_ids)

            semantic_ranked_lists: list[list[Fragment]] = []
            if question_context_fragments_request.semantic_queries:
                vectors = await asyncio.gather(*[
                    self._get_query_embedding(q.text) for q in question_context_fragments_request.semantic_queries
                ])
                fragment_lists: list[list[Fragment]] = []
                for q, vector in zip(question_context_fragments_request.semantic_queries, vectors, strict=True):
                    fragment_lists.append(
                        await self._retrieve_similar_fragments(
                            database_session=database_session,
                            query_vector=vector,
                            k=q.max_fragments,
                            document_ids=accessible_doc_ids,
                        )
                    )
                semantic_ranked_lists = fragment_lists

            bm25_ranked_lists: list[list[Fragment]] = []
            bm25_used = False
            if question_context_fragments_request.bm25_queries:
                try:
                    bm25_results: list[list[Fragment]] = []
                    for q in question_context_fragments_request.bm25_queries:
                        bm25_results.append(
                            await self._retrieve_bm25_fragments(
                                database_session=database_session,
                                query_text=q.text,
                                k=q.max_fragments,
                                document_ids=accessible_doc_ids,
                            )
                        )
                    bm25_ranked_lists = bm25_results
                    bm25_used = True
                except FragmentQueryRetrievalException:
                    await database_session.rollback()
                    logger.warning(
                        "BM25 retrieval failed; falling back to vector-only pool.",
                        exc_info=True,
                        extra={"user_id": authenticated_user.id},
                    )

            all_ranked_lists = semantic_ranked_lists + bm25_ranked_lists
            if len(all_ranked_lists) > 1:
                fragments: list[Fragment] = _reciprocal_rank_fusion(
                    ranked_lists=all_ranked_lists,
                    k=self._settings.bm25_rrf_k,
                )
            elif len(all_ranked_lists) == 1:
                fragments = all_ranked_lists[0]
            else:
                fragments = []

            fragments = [f for f in fragments if f.document_id in accessible_doc_set]

            rerank_applied = False
            if question_context_fragments_request.rerank.enabled and fragments:
                rerank_query = self._build_rerank_query(question_context_fragments_request)
                top_n = question_context_fragments_request.rerank.max_fragments
                indices = await self._reranker_factory.reranker.rerank(
                    query=rerank_query,
                    candidates=[f.content for f in fragments],
                    top_n=top_n,
                )
                fragments = [fragments[i] for i in indices]
                rerank_applied = True

            adjacent_added = 0
            if question_context_fragments_request.adjacent_chunks > 0 and fragments:
                retrieved_ids = {f.id for f in fragments}
                adjacent = await self._fragment_repository.get_adjacent_fragments(
                    fragments=fragments,
                    window=question_context_fragments_request.adjacent_chunks,
                    database_session=database_session,
                    exclude_ids=retrieved_ids,
                )
                adjacent = [f for f in adjacent if f.document_id in accessible_doc_set]
                adjacent_added = len(adjacent)
                fragments = fragments + adjacent

            seen_ids: set[int] = set()
            deduped: list[Fragment] = []
            for f in fragments:
                if f.id not in seen_ids:
                    seen_ids.add(f.id)
                    deduped.append(f)
            fragments = deduped

            fragment_responses = await self._build_fragment_responses(
                fragments=fragments,
                database_session=database_session,
            )

            logger.info(
                "Context fragments were retrieved successfully for the question.",
                extra={
                    "fragment_count": len(fragment_responses),
                    "rerank_applied": rerank_applied,
                    "bm25_used": bm25_used,
                    "adjacent_added": adjacent_added,
                },
            )
            return FragmentListResponse(fragments=fragment_responses)

        except (
                FragmentQueryNotFoundException,
                UnauthorizedException,
                FragmentQueryInvalidRequestException,
                FragmentQueryEmbeddingException,
                FragmentQueryRetrievalException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while retrieving context fragments by question.",
                extra={"semantic_query_count": len(question_context_fragments_request.semantic_queries)},
            )
            raise FragmentQueryServiceException(
                "An unexpected error occurred while retrieving context fragments for the question."
            ) from e

    async def retrieve_context_fragments_by_documents(
            self,
            documents_context_fragments_request: DocumentsContextFragmentsRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser,
            authorization_header: str | None = None,
    ) -> FragmentListResponse:
        logger.info(
            "Retrieving context fragments by documents was initiated.",
            extra={
                "document_ids_count": len(documents_context_fragments_request.document_ids),
                "user_id": authenticated_user.id,
            },
        )
        logger.debug(
            "Context fragment request includes the following document IDs.",
            extra={"document_ids": documents_context_fragments_request.document_ids},
        )

        try:
            documents = await self._get_documents_by_ids_or_raise(
                document_ids=documents_context_fragments_request.document_ids,
                database_session=database_session,
            )
            collection_doc_ids = await self._document_collection_catalog_client.fetch_all_accessible_document_ids(
                user_id=int(authenticated_user.id),
                authorization_header=authorization_header,
            )
            logger.debug(
                "Accessible document IDs fetched from collection service.",
                extra={
                    "user_id": authenticated_user.id,
                    "collection_doc_count": len(collection_doc_ids),
                },
            )
            allowed_ids = set(documents_context_fragments_request.document_ids) & collection_doc_ids
            if len(allowed_ids) != len(set(documents_context_fragments_request.document_ids)):
                logger.warning(
                    "Unauthorized or missing documents in fragments-by-documents request.",
                    extra={
                        "user_id": authenticated_user.id,
                        "requested_ids": documents_context_fragments_request.document_ids,
                    },
                )
                raise UnauthorizedException("You are not authorized to access one or more of these documents.")

            fragments = await self._retrieve_documents_fragments(
                database_session=database_session,
                document_ids=documents_context_fragments_request.document_ids,
            )

            docs_by_id = {doc.id: doc for doc in documents}
            fragment_responses = self._assemble_fragment_responses(
                fragments=fragments,
                docs_by_id=docs_by_id,
            )

            logger.info(
                "Context fragments were retrieved successfully for the documents.",
                extra={
                    "document_ids_count": len(documents_context_fragments_request.document_ids),
                    "fragment_count": len(fragment_responses),
                },
            )
            return FragmentListResponse(fragments=fragment_responses)

        except (
                FragmentQueryNotFoundException,
                UnauthorizedException,
                FragmentQueryInvalidRequestException,
                FragmentQueryEmbeddingException,
                FragmentQueryRetrievalException,
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while retrieving context fragments by documents.",
                extra={"document_ids_count": len(documents_context_fragments_request.document_ids)},
            )
            raise FragmentQueryServiceException(
                "An unexpected error occurred while retrieving context fragments for the documents."
            ) from e

    @staticmethod
    def _build_rerank_query(question_context_fragments_request: QuestionContextFragmentsRequest) -> str:
        if question_context_fragments_request.semantic_queries:
            return question_context_fragments_request.semantic_queries[0].text
        if question_context_fragments_request.bm25_queries:
            return question_context_fragments_request.bm25_queries[0].text
        return ""

    async def _build_fragment_responses(
            self,
            fragments: list[Fragment],
            database_session: AsyncSession,
    ) -> list[FragmentResponse]:
        if not fragments:
            return []

        document_ids = list({f.document_id for f in fragments})
        documents = await self._document_repository.get_documents_by_ids(
            document_ids=document_ids,
            database_session=database_session,
        )
        docs_by_id = {doc.id: doc for doc in documents}
        return self._assemble_fragment_responses(fragments=fragments, docs_by_id=docs_by_id)

    @staticmethod
    def _assemble_fragment_responses(
            fragments: list[Fragment],
            docs_by_id: dict[int, Document],
    ) -> list[FragmentResponse]:
        responses: list[FragmentResponse] = []
        for fragment in fragments:
            doc = docs_by_id.get(fragment.document_id)
            if doc is None:
                logger.warning(
                    "Document not found for fragment; skipping.",
                    extra={"fragment_id": fragment.id, "document_id": fragment.document_id},
                )
                continue
            responses.append(
                FragmentResponse.model_validate(
                    {
                        "id": fragment.id,
                        "content": fragment.content,
                        "fragment_index": fragment.fragment_index,
                        "summary": fragment.summary,
                        "entities": fragment.entities,
                        "topics": list(fragment.topics) if fragment.topics else None,
                        "document": {
                            "id": doc.id,
                            "name": doc.name,
                            "description": doc.description,
                            "type": doc.type,
                            "category": doc.category,
                        },
                    }
                )
            )
        return responses

    async def _get_documents_by_ids_or_raise(
            self,
            document_ids: list[int],
            database_session: AsyncSession,
    ) -> list[Document]:
        documents = await self._document_repository.get_documents_by_ids(
            document_ids=document_ids,
            database_session=database_session,
        )
        found_ids = {doc.id for doc in documents}
        missing = sorted(set(document_ids) - found_ids)
        if missing:
            logger.warning(
                "Some documents were not found.",
                extra={"not_found_document_ids": missing},
            )
            raise FragmentQueryNotFoundException("One or more documents were not found.")
        return documents

    async def _get_query_embedding(self, text: str) -> list[float]:
        try:
            vector: list[float] = await self._embedder_factory.embedder.aembed_query(text=text)
            logger.debug("Query embedding generated.", extra={"text_length": len(text)})
            return vector
        except Exception as e:
            raise FragmentQueryEmbeddingException("Failed to generate the query embedding.") from e

    async def _retrieve_similar_fragments(
            self,
            database_session: AsyncSession,
            query_vector: list[float],
            k: int,
            document_ids: list[int] | None = None,
    ) -> list[Fragment]:
        try:
            fragments = await self._fragment_repository.get_most_similar_fragments(
                query_vector=query_vector,
                database_session=database_session,
                k=k,
                threshold=self._settings.similarity_threshold,
                document_ids=document_ids,
            )
            logger.debug("Similar fragments retrieved.", extra={"fragment_count": len(fragments)})
            return fragments
        except Exception as e:
            raise FragmentQueryRetrievalException("Failed to retrieve similar fragments.") from e

    async def _retrieve_bm25_fragments(
            self,
            database_session: AsyncSession,
            query_text: str,
            k: int,
            document_ids: list[int] | None = None,
    ) -> list[Fragment]:
        try:
            return await self._fragment_repository.get_most_relevant_fragments_bm25(
                query=query_text,
                database_session=database_session,
                k=k,
                min_score=self._settings.bm25_min_score,
                query_max_chars=self._settings.bm25_query_max_chars,
                document_ids=document_ids,
            )
        except Exception as e:
            raise FragmentQueryRetrievalException("Failed to retrieve BM25-ranked fragments.") from e

    async def _retrieve_documents_fragments(
            self,
            database_session: AsyncSession,
            document_ids: list[int],
    ) -> list[Fragment]:
        try:
            fragments = await self._fragment_repository.get_fragments_by_document_ids(
                document_ids=document_ids,
                database_session=database_session,
            )
            logger.debug(
                "Fragments retrieved for the documents.",
                extra={"document_ids_count": len(document_ids), "fragment_count": len(fragments)},
            )
            return fragments
        except Exception as e:
            raise FragmentQueryRetrievalException("Failed to retrieve fragments for the documents.") from e
