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
from app.application.services.fragment.fragment_query_service.fragment_context_reranker import (
    FragmentContextReranker
)
from app.application.services.fragment.fragment_query_service.hybrid_fusion import (
    reciprocal_rank_fusion,
)
from app.application.services.fragment.fragment_query_service.fragment_query_service_settings import (
    FragmentQueryServiceSettings
)
from app.application.services.fragment.fragment_query_service.interfaces.fragment_query_service_interface import (
    FragmentQueryServiceInterface
)
from app.domain.dtos.fragment.fragment_query.documents_context_fragments_request import (
    DocumentsContextFragmentsRequest
)
from app.domain.dtos.fragment.fragment_query.fragment_list_response import FragmentListResponse
from app.domain.dtos.fragment.fragment_query.question_context_fragments_request import (
    QuestionContextFragmentsRequest
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.orm.fragment import Fragment
from app.infrastructure.persistence.database.repositories.document_collection_repository.document_collection_repository_interface import (
    DocumentCollectionRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_interface import (
    FragmentRepositoryInterface
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
            fragment_query_service_settings: Optional[FragmentQueryServiceSettings] = None
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._embedder_factory = embedder_factory
        self._settings = fragment_query_service_settings or FragmentQueryServiceSettings()
        self._authorizer = authorizer
        self._document_collection_repository = document_collection_repository
        self._reranker = FragmentContextReranker(fragment_query_service_settings=self._settings)

    @staticmethod
    def _merge_distinct_fragments(primary: list, secondary: list) -> list:
        seen: set[int] = set()
        merged: list = []
        for fragment in primary:
            fid = int(fragment.id)
            if fid not in seen:
                seen.add(fid)
                merged.append(fragment)
        for fragment in secondary:
            fid = int(fragment.id)
            if fid not in seen:
                seen.add(fid)
                merged.append(fragment)
        return merged

    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> FragmentListResponse:
        question = question_context_fragments_request.question
        question_max_fragments = question_context_fragments_request.question_max_fragments
        use_keywords = question_context_fragments_request.use_keywords is True
        use_bm25 = question_context_fragments_request.use_bm25 is True

        logger.info(
            "Retrieving context fragments by question was initiated.",
            extra={
                "question_length": len(question),
                "question_max_fragments": question_max_fragments,
                "user_id": authenticated_user.id,
                "use_keywords": use_keywords,
                "use_bm25": use_bm25,
                "use_rerank": question_context_fragments_request.use_rerank is True,
            }
        )

        try:
            self._authorizer.require_permissions(
                authenticated_user=authenticated_user,
                required_permissions=frozenset({
                    Permissions.LIST_CONTEXT_FRAGMENTS_BY_QUESTION,
                }),
            )

            if question_context_fragments_request.question_max_fragments > self._settings.max_fragments:
                raise FragmentQueryInvalidRequestException(
                    "The maximum number of context fragments for the question exceeds the configured limit."
                )
            if (question_context_fragments_request.use_keywords is True
                    and question_context_fragments_request.keywords_max_fragments is not None
                    and question_context_fragments_request.keywords_max_fragments > self._settings.max_fragments):
                raise FragmentQueryInvalidRequestException(
                    "The maximum number of context fragments for keywords exceeds the configured limit."
                )
            if (
                    question_context_fragments_request.use_bm25 is True
                    and question_context_fragments_request.bm25_max_fragments is not None
                    and question_context_fragments_request.bm25_max_fragments > self._settings.max_fragments
            ):
                raise FragmentQueryInvalidRequestException(
                    "The maximum number of BM25 fragments exceeds the configured limit."
                )
            if question_context_fragments_request.use_rerank is True and not self._settings.rerank_enabled:
                raise FragmentQueryInvalidRequestException("Reranking is disabled on this service.")
            if question_context_fragments_request.use_bm25 is True and not self._settings.bm25_enabled:
                raise FragmentQueryInvalidRequestException("BM25 retrieval is disabled on this service.")

            if use_keywords:
                keywords = question_context_fragments_request.keywords
                keywords_max_fragments = question_context_fragments_request.keywords_max_fragments
                question_vector, keywords_vector = await asyncio.gather(
                    self._get_query_embedding(question),
                    self._get_query_embedding(keywords),
                )
                fragments_from_question, fragments_from_keywords = await asyncio.gather(
                    self._retrieve_similar_fragments(
                        database_session=database_session,
                        query_vector=question_vector,
                        k=question_max_fragments,
                    ),
                    self._retrieve_similar_fragments(
                        database_session=database_session,
                        query_vector=keywords_vector,
                        k=keywords_max_fragments,
                    ),
                )
            else:
                question_vector = await self._get_query_embedding(question)
                fragments_from_question = await self._retrieve_similar_fragments(
                    database_session=database_session,
                    query_vector=question_vector,
                    k=question_max_fragments,
                )
                fragments_from_keywords = None

            bm25_requested = use_bm25 and self._settings.bm25_enabled
            bm25_used = False
            bm25_count = 0

            if bm25_requested:
                try:
                    fragments_from_bm25 = await self._retrieve_bm25_fragments(
                        database_session=database_session,
                        query_text=question,
                        k=question_context_fragments_request.bm25_max_fragments,
                    )
                    bm25_count = len(fragments_from_bm25)
                    bm25_used = True

                    ranked_lists: list[list[Fragment]] = [fragments_from_question]
                    if use_keywords and fragments_from_keywords is not None:
                        ranked_lists.append(fragments_from_keywords)
                    ranked_lists.append(fragments_from_bm25)

                    fragments = reciprocal_rank_fusion(
                        ranked_lists=ranked_lists,
                        k=self._settings.bm25_rrf_k,
                    )
                except FragmentQueryRetrievalException:
                    logger.warning(
                        "BM25 retrieval failed; falling back to vector-only retrieval pool.",
                        exc_info=True,
                        extra={"user_id": authenticated_user.id},
                    )
                    if use_keywords and fragments_from_keywords is not None:
                        fragments = self._merge_distinct_fragments(
                            fragments_from_question,
                            fragments_from_keywords,
                        )
                    else:
                        fragments = fragments_from_question
            elif use_keywords and fragments_from_keywords is not None:
                fragments = self._merge_distinct_fragments(
                    fragments_from_question,
                    fragments_from_keywords,
                )
            else:
                fragments = fragments_from_question

            fragments = await self._filter_accessible_fragments(
                fragments=fragments,
                user_id=authenticated_user.id,
                chat_id=question_context_fragments_request.chat_id,
                database_session=database_session
            )
            post_acl_pool_count = len(fragments)

            rerank_requested = (
                    self._settings.rerank_enabled
                    and question_context_fragments_request.use_rerank is True
            )
            rerank_applied = False
            if rerank_requested and len(fragments) >= self._settings.rerank_min_fragments:
                top_n = question_context_fragments_request.rerank_max_fragments
                fragments = await self._reranker.rerank_fragments(
                    query=question,
                    fragments=fragments,
                    top_n=top_n,
                )
                rerank_applied = True
            elif rerank_requested:
                logger.debug(
                    "Rerank skipped: fragment count below configured minimum.",
                    extra={
                        "fragment_count": len(fragments),
                        "rerank_min_fragments": self._settings.rerank_min_fragments,
                    },
                )

            document_ids = list({fragment.document_id for fragment in fragments})
            documents = await self._document_repository.get_documents_by_ids(
                document_ids=document_ids,
                database_session=database_session
            )

            logger.info(
                "Context fragments were retrieved successfully for the question.",
                extra={
                    "question_length": len(question),
                    "fragment_count": len(fragments),
                    "document_count": len(documents),
                    "rerank_applied": rerank_applied,
                    # ``bm25_used`` = retrieval branch ran without error; rows may still be zero.
                    "bm25_used": bm25_used,
                    "bm25_candidate_count": bm25_count,
                    "bm25_had_matches": bm25_count > 0,
                    "pre_rerank_pool_count": post_acl_pool_count,
                    "rerank_requested": rerank_requested,
                },
            )
            return FragmentListResponse(fragments=fragments, documents=documents)

        except (
                FragmentQueryNotFoundException,
                UnauthorizedException,
                FragmentQueryInvalidRequestException,
                FragmentQueryEmbeddingException,
                FragmentQueryRetrievalException
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while retrieving context fragments by question.",
                extra={
                    "question_length": len(question)
                }
            )
            raise FragmentQueryServiceException(
                "An unexpected error occurred while retrieving context fragments for the question."
            ) from e

    async def retrieve_context_fragments_by_documents(
            self,
            documents_context_fragments_request: DocumentsContextFragmentsRequest,
            database_session: AsyncSession,
            authenticated_user: AuthenticatedUser
    ) -> FragmentListResponse:
        document_ids = documents_context_fragments_request.document_ids

        logger.info(
            "Retrieving context fragments by documents was initiated.",
            extra={
                "document_ids_count": len(document_ids),
                "user_id": authenticated_user.id
            }
        )
        logger.debug(
            "Context fragment request includes the following document IDs.",
            extra={
                "document_ids": document_ids
            }
        )

        try:
            self._authorizer.require_permissions(
                authenticated_user=authenticated_user,
                required_permissions=frozenset({
                    Permissions.LIST_CONTEXT_FRAGMENTS_BY_DOCUMENTS,
                }),
            )

            if len(documents_context_fragments_request.document_ids) > self._settings.max_document_ids:
                raise FragmentQueryInvalidRequestException(
                    "The number of document identifiers exceeds the configured limit."
                )

            documents = await self._get_documents_by_ids_or_raise(
                document_ids=document_ids,
                database_session=database_session
            )
            for document in documents:
                self._authorizer.require_document_ownership(
                    document=document,
                    authenticated_user=authenticated_user,
                )

            all_fragments = await self._retrieve_documents_fragments(
                database_session=database_session,
                document_ids=document_ids
            )

            logger.info(
                "Context fragments were retrieved successfully for the documents.",
                extra={
                    "document_ids_count": len(document_ids),
                    "fragment_count": len(all_fragments)
                }
            )
            return FragmentListResponse(
                fragments=all_fragments,
                documents=documents
            )

        except (
                FragmentQueryNotFoundException,
                UnauthorizedException,
                FragmentQueryInvalidRequestException,
                FragmentQueryEmbeddingException,
                FragmentQueryRetrievalException
        ):
            raise
        except Exception as e:
            logger.exception(
                "An unexpected error occurred while retrieving context fragments by documents.",
                extra={
                    "document_ids_count": len(document_ids)
                }
            )
            raise FragmentQueryServiceException(
                "An unexpected error occurred while retrieving context fragments for the documents."
            ) from e

    async def _filter_accessible_fragments(
            self,
            fragments: list[Fragment],
            user_id: int,
            chat_id: Optional[int],
            database_session: AsyncSession
    ) -> list:
        document_ids = list({fragment.document_id for fragment in fragments})
        if not document_ids:
            return fragments

        accessible_ids = await self._document_collection_repository.get_accessible_document_ids(
            user_id=user_id,
            document_ids=document_ids,
            chat_id=chat_id,
            database_session=database_session
        )

        if not accessible_ids:
            return []

        return [f for f in fragments if f.document_id in accessible_ids]

    async def _get_documents_by_ids_or_raise(
            self,
            document_ids: list[int],
            database_session: AsyncSession
    ) -> list[Document]:
        documents = await self._document_repository.get_documents_by_ids(
            document_ids=document_ids,
            database_session=database_session
        )
        found_ids = {document.id for document in documents}
        requested_ids = set(document_ids)
        not_found = sorted(requested_ids - found_ids)
        if not_found:
            logger.warning(
                "Some documents were not found.",
                extra={
                    "not_found_document_ids": not_found
                }
            )
            raise FragmentQueryNotFoundException("One or more documents were not found.")
        return documents

    async def _get_query_embedding(
            self,
            question: str
    ) -> list[float]:
        try:
            embedder = self._embedder_factory.embedder
            vector: list[float] = await embedder.aembed_query(text=question)
            logger.debug(
                "The query embedding was generated.",
                extra={
                    "question_length": len(question)
                }
            )
            return vector
        except Exception as e:
            raise FragmentQueryEmbeddingException("Failed to generate the query embedding.") from e

    async def _retrieve_similar_fragments(
            self,
            database_session: AsyncSession,
            query_vector: list[float],
            k: int
    ) -> list[Fragment]:
        try:
            fragments = await self._fragment_repository.get_most_similar_fragments(
                query_vector=query_vector,
                database_session=database_session,
                k=k,
                threshold=self._settings.similarity_threshold
            )
            logger.debug(
                "Similar fragments were retrieved.",
                extra={
                    "fragment_count": len(fragments)
                }
            )
            return fragments
        except Exception as e:
            raise FragmentQueryRetrievalException("Failed to retrieve similar fragments.") from e

    async def _retrieve_bm25_fragments(
            self,
            *,
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
            document_ids: list[int]
    ) -> list:
        try:
            fragments = await self._fragment_repository.get_fragments_by_document_ids(
                document_ids=document_ids,
                database_session=database_session
            )
            logger.debug(
                "Fragments were retrieved for the documents.",
                extra={
                    "document_ids_count": len(document_ids),
                    "fragment_count": len(fragments)
                }
            )
            return fragments
        except Exception as e:
            raise FragmentQueryRetrievalException("Failed to retrieve fragments for the documents.") from e


async def get_fragment_query_service(
        request: Request
) -> FragmentQueryServiceInterface:
    try:
        return request.app.state.fragment_query_service
    except AttributeError:
        logger.error("FragmentQueryService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FragmentQueryService is not registered on the application state."
        )
