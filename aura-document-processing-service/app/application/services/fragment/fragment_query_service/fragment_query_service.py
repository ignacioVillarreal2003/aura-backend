import asyncio
import logging
from typing import Optional
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.authorization.permissions import Permissions
from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.services.fragment.fragment_query_service.exceptions.fragment_query_service_exception import (
    FragmentQueryEmbeddingException,
    FragmentQueryInvalidRequestException,
    FragmentQueryNotFoundException,
    FragmentQueryRetrievalException,
    FragmentQueryServiceException,
)
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.services.fragment.fragment_query_service.fragment_reranker import FragmentReranker
from app.application.services.fragment.fragment_query_service.hybrid_fusion import (
    reciprocal_rank_fusion,
)
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
from app.infrastructure.persistence.database.repositories.document_collection_repository.document_collection_repository_interface import (
    DocumentCollectionRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)


class FragmentQueryService(FragmentQueryServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            embedder_factory: EmbedderFactory,
            authorizer: Authorizer,
            document_collection_repository: DocumentCollectionRepositoryInterface,
            document_collection_catalog_client: DocumentCollectionCatalogClientInterface,
            fragment_query_service_settings: Optional[FragmentQueryServiceSettings] = None,
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._embedder_factory = embedder_factory
        self._settings = fragment_query_service_settings or FragmentQueryServiceSettings()
        self._authorizer = authorizer
        self._document_collection_repository = document_collection_repository
        self._document_collection_catalog_client = document_collection_catalog_client
        self._reranker = FragmentReranker(fragment_query_service_settings=self._settings)

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
            self._authorizer.require_permissions(
                authenticated_user=authenticated_user,
                required_permissions=frozenset({Permissions.LIST_CONTEXT_FRAGMENTS_BY_QUESTION}),
            )

            self._validate_query_request_against_settings(question_context_fragments_request)

            semantic_ranked_lists: list[list[Fragment]] = []
            if question_context_fragments_request.semantic_queries:
                vectors = await asyncio.gather(*[
                    self._get_query_embedding(q.text) for q in question_context_fragments_request.semantic_queries
                ])
                fragment_lists: list[list[Fragment]] = []
                for q, vector in zip(question_context_fragments_request.semantic_queries, vectors):
                    fragment_lists.append(
                        await self._retrieve_similar_fragments(
                            database_session=database_session,
                            query_vector=vector,
                            k=q.max_fragments,
                        )
                    )
                semantic_ranked_lists = fragment_lists

            bm25_ranked_lists: list[list[Fragment]] = []
            bm25_used = False
            if question_context_fragments_request.bm25_queries and self._settings.bm25_enabled:
                try:
                    bm25_results: list[list[Fragment]] = []
                    for q in question_context_fragments_request.bm25_queries:
                        bm25_results.append(
                            await self._retrieve_bm25_fragments(
                                database_session=database_session,
                                query_text=q.text,
                                k=q.max_fragments,
                            )
                        )
                    bm25_ranked_lists = bm25_results
                    bm25_used = True
                except FragmentQueryRetrievalException:
                    logger.warning(
                        "BM25 retrieval failed; falling back to vector-only pool.",
                        exc_info=True,
                        extra={"user_id": authenticated_user.id},
                    )

            all_ranked_lists = semantic_ranked_lists + bm25_ranked_lists
            if len(all_ranked_lists) > 1:
                fragments: list[Fragment] = reciprocal_rank_fusion(
                    ranked_lists=all_ranked_lists,
                    k=self._settings.bm25_rrf_k,
                )
            elif len(all_ranked_lists) == 1:
                fragments = all_ranked_lists[0]
            else:
                fragments = []

            fragments = await self._filter_accessible_fragments(
                fragments=fragments,
                user_id=authenticated_user.id,
                chat_id=question_context_fragments_request.chat_id,
                database_session=database_session,
                authorization_header=authorization_header,
            )
            pre_rerank_count = len(fragments)

            rerank_applied = False
            if question_context_fragments_request.rerank.enabled and self._settings.rerank_enabled:
                if pre_rerank_count >= self._settings.rerank_min_fragments:
                    rerank_query = self._build_rerank_query(question_context_fragments_request)
                    fragments = await self._reranker.rerank_fragments(
                        query=rerank_query,
                        fragments=fragments,
                        top_n=question_context_fragments_request.rerank.max_fragments,
                    )
                    rerank_applied = True
                else:
                    logger.info(
                        "Rerank skipped: fragment count is below rerank_min_fragments.",
                        extra={
                            "fragment_count": pre_rerank_count,
                            "rerank_min_fragments": self._settings.rerank_min_fragments,
                        },
                    )

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
                    "pre_rerank_count": pre_rerank_count,
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
            self._authorizer.require_permissions(
                authenticated_user=authenticated_user,
                required_permissions=frozenset({Permissions.LIST_CONTEXT_FRAGMENTS_BY_DOCUMENTS}),
            )

            if len(documents_context_fragments_request.document_ids) > self._settings.max_document_ids:
                raise FragmentQueryInvalidRequestException(
                    "The number of document identifiers exceeds the configured limit."
                )

            documents = await self._get_documents_by_ids_or_raise(
                document_ids=documents_context_fragments_request.document_ids,
                database_session=database_session,
            )
            collection_ids = await self._document_collection_catalog_client.fetch_all_accessible_collection_ids(
                user_id=int(authenticated_user.id),
                authorization_header=authorization_header,
            )
            allowed_ids = await self._document_collection_repository.get_accessible_document_ids(
                user_id=int(authenticated_user.id),
                document_ids=documents_context_fragments_request.document_ids,
                chat_id=None,
                accessible_collection_ids=collection_ids,
                database_session=database_session,
            )
            if len(allowed_ids) != len(documents_context_fragments_request.document_ids):
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

    def _validate_query_request_against_settings(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
    ) -> None:
        for q in question_context_fragments_request.semantic_queries:
            if q.max_fragments > self._settings.max_fragments:
                raise FragmentQueryInvalidRequestException(
                    "A semantic query requests more fragments than the configured limit."
                )
        if question_context_fragments_request.bm25_queries and not self._settings.bm25_enabled:
            raise FragmentQueryInvalidRequestException(
                "BM25 retrieval is disabled on this service."
            )
        for q in question_context_fragments_request.bm25_queries:
            if q.max_fragments > self._settings.max_fragments:
                raise FragmentQueryInvalidRequestException(
                    "A BM25 query requests more fragments than the configured limit."
                )
        if question_context_fragments_request.rerank.enabled and not self._settings.rerank_enabled:
            raise FragmentQueryInvalidRequestException(
                "Reranking is disabled on this service."
            )

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

    async def _filter_accessible_fragments(
            self,
            fragments: list[Fragment],
            user_id: int,
            chat_id: Optional[int],
            database_session: AsyncSession,
            authorization_header: str | None,
    ) -> list[Fragment]:
        document_ids = list({fragment.document_id for fragment in fragments})
        if not document_ids:
            return fragments

        collection_ids = await self._document_collection_catalog_client.fetch_all_accessible_collection_ids(
            user_id=int(user_id),
            authorization_header=authorization_header,
        )
        accessible_ids = await self._document_collection_repository.get_accessible_document_ids(
            user_id=user_id,
            document_ids=document_ids,
            chat_id=chat_id,
            accessible_collection_ids=collection_ids,
            database_session=database_session,
        )

        if not accessible_ids:
            return []

        return [f for f in fragments if f.document_id in accessible_ids]

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
    ) -> list[Fragment]:
        try:
            fragments = await self._fragment_repository.get_most_similar_fragments(
                query_vector=query_vector,
                database_session=database_session,
                k=k,
                threshold=self._settings.similarity_threshold,
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
    ) -> list[Fragment]:
        try:
            return await self._fragment_repository.get_most_relevant_fragments_bm25(
                query=query_text,
                database_session=database_session,
                k=k,
                min_score=self._settings.bm25_min_score,
                query_max_chars=self._settings.bm25_query_max_chars,
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


async def get_fragment_query_service(request: Request) -> FragmentQueryServiceInterface:
    try:
        return request.app.state.fragment_query_service
    except AttributeError:
        logger.error("FragmentQueryService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FragmentQueryService is not registered on the application state.",
        )
