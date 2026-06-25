import asyncio
import logging
from typing import Any, Literal, Optional, Protocol, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.rerankers.reranker_factory import RerankerFactory
from app.configuration.metrics import (
    retrieval_lane_fragments_total,
    retrieval_top_rerank_score,
)
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
from app.domain.dtos.fragment.fragment_query.fragment_list_response import (
    FragmentListResponse,
    FragmentSectionGroup,
)
from app.domain.dtos.fragment.fragment_query.fragment_response import FragmentResponse
from app.domain.dtos.fragment.fragment_query.question_context_fragments_request import (
    QuestionContextFragmentsRequest,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.request_token import get_request_token
from app.infrastructure.http.chat_membership.interfaces.chat_membership_provider_interface import (
    ChatMembershipProviderInterface,
)
from app.infrastructure.http.document_collection_catalog.interfaces.document_collection_catalog_client_interface import (
    DocumentCollectionCatalogClientInterface,
)
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.orm.fragment import Fragment
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)


class _HasId(Protocol):
    id: Any


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
            chat_membership_provider: ChatMembershipProviderInterface,
            database_manager: DatabaseManagerInterface,
            fragment_query_service_settings: Optional[FragmentQueryServiceSettings] = None,
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._embedder_factory = embedder_factory
        self._reranker_factory = reranker_factory
        self._settings = fragment_query_service_settings or FragmentQueryServiceSettings()
        self._document_collection_catalog_client = document_collection_catalog_client
        self._chat_membership_provider = chat_membership_provider
        self._database_manager = database_manager

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
            token = authorization_header or get_request_token()

            if question_context_fragments_request.chat_id is not None:
                collection_doc_ids, membership = await asyncio.gather(
                    self._document_collection_catalog_client.fetch_all_accessible_document_ids(
                        user_id=int(authenticated_user.id),
                        authorization_header=token,
                    ),
                    self._chat_membership_provider.get_membership(
                        chat_id=int(question_context_fragments_request.chat_id),
                        user_id=int(authenticated_user.id),
                        authorization_header=token,
                    ),
                )
            else:
                collection_doc_ids = await self._document_collection_catalog_client.fetch_all_accessible_document_ids(
                    user_id=int(authenticated_user.id),
                    authorization_header=token,
                )
                membership = None

            accessible_doc_set: set[int] = set(collection_doc_ids)

            chat_doc_count = 0
            if (
                membership is not None
                and membership.is_member
                and question_context_fragments_request.chat_id is not None
            ):
                chat_documents = await self._document_repository.get_documents_by_chat_id(
                    chat_id=int(question_context_fragments_request.chat_id),
                    database_session=database_session,
                )
                chat_doc_ids = {int(doc.id) for doc in chat_documents}
                chat_doc_count = len(chat_doc_ids)
                accessible_doc_set |= chat_doc_ids

            logger.debug(
                "Accessible document IDs resolved.",
                extra={
                    "user_id": authenticated_user.id,
                    "collection_doc_count": len(collection_doc_ids),
                    "chat_doc_count": chat_doc_count,
                },
            )
            accessible_doc_ids = list(accessible_doc_set)

            if not accessible_doc_ids:
                logger.info(
                    "No accessible documents for the user; returning an empty fragment list.",
                    extra={"user_id": authenticated_user.id},
                )
                return FragmentListResponse(fragments=[])

            semantic_queries = question_context_fragments_request.semantic_queries
            bm25_queries = question_context_fragments_request.bm25_queries
            retrieval_semaphore = asyncio.Semaphore(self._settings.max_retrieval_concurrency)

            vectors: list[list[float]] = []
            if semantic_queries:
                vectors = await asyncio.gather(*[
                    self._get_query_embedding(q.text) for q in semantic_queries
                ])

            semantic_coros = [
                self._retrieve_similar_isolated(
                    query_vector=vector,
                    k=q.max_fragments,
                    document_ids=accessible_doc_ids,
                    semaphore=retrieval_semaphore,
                )
                for q, vector in zip(semantic_queries, vectors, strict=True)
            ]
            contextual_coros = []
            if self._settings.contextual_retrieval_enabled:
                contextual_coros = [
                    self._retrieve_similar_isolated(
                        query_vector=vector,
                        k=q.max_fragments,
                        document_ids=accessible_doc_ids,
                        semaphore=retrieval_semaphore,
                        representation="contextual",
                    )
                    for q, vector in zip(semantic_queries, vectors, strict=True)
                ]
            bm25_coros = [
                self._retrieve_bm25_isolated(
                    query_text=q.text,
                    k=q.max_fragments,
                    document_ids=accessible_doc_ids,
                    semaphore=retrieval_semaphore,
                )
                for q in bm25_queries
            ]
            if self._settings.contextual_retrieval_enabled:
                bm25_coros += [
                    self._retrieve_bm25_isolated(
                        query_text=q.text,
                        k=q.max_fragments,
                        document_ids=accessible_doc_ids,
                        semaphore=retrieval_semaphore,
                        representation="contextual",
                    )
                    for q in bm25_queries
                ]

            semantic_ranked_lists, contextual_ranked_lists, bm25_results = await asyncio.gather(
                asyncio.gather(*semantic_coros),
                asyncio.gather(*contextual_coros),
                asyncio.gather(*bm25_coros, return_exceptions=True),
            )

            bm25_ranked_lists: list[list[Fragment]] = []
            bm25_used = False
            if bm25_coros:
                bm25_failure = next(
                    (r for r in bm25_results if isinstance(r, BaseException)), None
                )
                if bm25_failure is not None:
                    logger.warning(
                        "BM25 retrieval failed; falling back to vector-only pool.",
                        exc_info=bm25_failure,
                        extra={"user_id": authenticated_user.id},
                    )
                else:
                    bm25_ranked_lists = [r for r in bm25_results if not isinstance(r, BaseException)]
                    bm25_used = True

            lane_ids = self._build_lane_membership(
                semantic_ranked_lists=semantic_ranked_lists,
                contextual_ranked_lists=contextual_ranked_lists,
                bm25_ranked_lists=bm25_ranked_lists,
                bm25_query_count=len(bm25_queries),
            )

            all_ranked_lists = (
                list(semantic_ranked_lists) + list(contextual_ranked_lists) + bm25_ranked_lists
            )
            if len(all_ranked_lists) > 1:
                fragments: list[Fragment] = _reciprocal_rank_fusion(
                    ranked_lists=all_ranked_lists,
                    k=self._settings.bm25_rrf_k,
                )
            elif len(all_ranked_lists) == 1:
                fragments = all_ranked_lists[0]
            else:
                fragments = []

            rerank_applied = False
            if question_context_fragments_request.rerank.enabled and fragments:
                fragments = fragments[:self._settings.rerank_candidate_pool_cap]
                rerank_query = self._build_rerank_query(question_context_fragments_request)
                top_n = question_context_fragments_request.rerank.max_fragments or len(fragments)
                scored = await self._reranker_factory.reranker.rerank_with_scores(
                    query=rerank_query,
                    candidates=[(f.contextualized_content or f.content) for f in fragments],
                    top_n=top_n,
                )
                fragments = [fragments[i] for i, _ in scored if 0 <= i < len(fragments)]
                self._record_top_rerank_score(scored)
                rerank_applied = True

            self._record_lane_contribution(fragments, lane_ids)

            expansion = question_context_fragments_request.context_expansion

            if expansion == "section" and fragments:
                response = await self._build_section_response(
                    primaries=fragments,
                    request=question_context_fragments_request,
                    database_session=database_session,
                    accessible_doc_set=accessible_doc_set,
                )
                logger.info(
                    "Context fragments were retrieved successfully for the question.",
                    extra={
                        "fragment_count": len(response.fragments),
                        "group_count": len(response.groups or []),
                        "rerank_applied": rerank_applied,
                        "bm25_used": bm25_used,
                        "context_expansion": expansion,
                    },
                )
                return response

            adjacent_added = 0
            if (
                expansion == "adjacent"
                and question_context_fragments_request.adjacent_chunks > 0
                and fragments
            ):
                retrieved_ids = {f.id for f in fragments}
                adjacent = await self._fragment_repository.get_adjacent_fragments(
                    fragments=fragments,
                    window=question_context_fragments_request.adjacent_chunks,
                    database_session=database_session,
                    exclude_ids=retrieved_ids,
                    respect_section_boundaries=self._settings.respect_section_boundaries,
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
                    "context_expansion": expansion,
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
            requested_ids: list[int] = [int(d) for d in documents_context_fragments_request.document_ids]
            documents = await self._get_documents_by_ids_or_raise(
                document_ids=requested_ids,
                database_session=database_session,
            )
            token = authorization_header or get_request_token()
            collection_doc_ids = await self._document_collection_catalog_client.fetch_all_accessible_document_ids(
                user_id=int(authenticated_user.id),
                authorization_header=token,
            )

            accessible_ids: set[int] = set(requested_ids) & set(collection_doc_ids)

            chats_to_check: dict[int, list[int]] = {}
            for document in documents:
                doc_id = int(document.id)
                if doc_id in accessible_ids or document.chat_id is None:
                    continue
                chats_to_check.setdefault(int(document.chat_id), []).append(doc_id)

            if chats_to_check:
                memberships = await asyncio.gather(*[
                    self._chat_membership_provider.get_membership(
                        chat_id=chat_id,
                        user_id=int(authenticated_user.id),
                        authorization_header=token,
                    )
                    for chat_id in chats_to_check
                ])
                for chat_id, membership in zip(chats_to_check, memberships, strict=True):
                    if membership.is_member:
                        accessible_ids.update(chats_to_check[chat_id])

            logger.debug(
                "Accessible document IDs resolved for documents request.",
                extra={
                    "user_id": authenticated_user.id,
                    "collection_doc_count": len(collection_doc_ids),
                    "chat_checked_count": len(chats_to_check),
                },
            )

            if len(accessible_ids) != len(set(requested_ids)):
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
                document_ids=requested_ids,
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
    def _build_lane_membership(
            *,
            semantic_ranked_lists: list[list[Fragment]],
            contextual_ranked_lists: list[list[Fragment]],
            bm25_ranked_lists: list[list[Fragment]],
            bm25_query_count: int,
    ) -> dict[str, set[int]]:
        def _ids(lists: list[list[Fragment]]) -> set[int]:
            return {int(f.id) for lst in lists for f in lst}

        return {
            "vector_raw": _ids(list(semantic_ranked_lists)),
            "vector_contextual": _ids(list(contextual_ranked_lists)),
            "bm25_raw": _ids(bm25_ranked_lists[:bm25_query_count]),
            "bm25_contextual": _ids(bm25_ranked_lists[bm25_query_count:]),
        }

    @staticmethod
    def _record_top_rerank_score(scored: list[tuple[int, float]]) -> None:
        if not scored:
            return
        try:
            top = max(score for _, score in scored)
            retrieval_top_rerank_score.observe(float(top))
        except Exception:
            logger.debug("Failed to record top rerank score metric.", exc_info=True)

    @staticmethod
    def _record_lane_contribution(
            fragments: list[Fragment],
            lane_ids: dict[str, set[int]],
    ) -> None:
        try:
            for fragment in fragments:
                fid = int(fragment.id)
                for lane, ids in lane_ids.items():
                    if fid in ids:
                        retrieval_lane_fragments_total.labels(lane=lane).inc()
        except Exception:
            logger.debug("Failed to record lane contribution metric.", exc_info=True)

    @staticmethod
    def _build_rerank_query(question_context_fragments_request: QuestionContextFragmentsRequest) -> str:
        if question_context_fragments_request.semantic_queries:
            return question_context_fragments_request.semantic_queries[0].text
        if question_context_fragments_request.bm25_queries:
            return question_context_fragments_request.bm25_queries[0].text
        return ""

    async def _build_section_response(
            self,
            *,
            primaries: list[Fragment],
            request: QuestionContextFragmentsRequest,
            database_session: AsyncSession,
            accessible_doc_set: set[int],
    ) -> FragmentListResponse:
        primary_ids = {f.id for f in primaries}
        half = max(self._settings.max_section_fragments // 2, 1)
        fallback_window = request.adjacent_chunks if request.adjacent_chunks > 0 else 1

        with_section = [p for p in primaries if p.section_path is not None]
        without_section = [p for p in primaries if p.section_path is None]

        pool: list[Fragment] = []
        if with_section:
            section_members = await self._fragment_repository.get_section_fragments(
                fragments=with_section,
                max_per_section=self._settings.max_section_fragments,
                database_session=database_session,
                exclude_ids=primary_ids,
            )
            pool.extend(f for f in section_members if f.document_id in accessible_doc_set)
        if without_section:
            adjacent_members = await self._fragment_repository.get_adjacent_fragments(
                fragments=without_section,
                window=fallback_window,
                database_session=database_session,
                exclude_ids=primary_ids,
                respect_section_boundaries=self._settings.respect_section_boundaries,
            )
            pool.extend(f for f in adjacent_members if f.document_id in accessible_doc_set)

        seen: set[int] = set()
        grouped_members: list[tuple[Fragment, list[Fragment]]] = []
        for primary in primaries:
            members = self._select_section_members(
                primary=primary,
                pool=pool,
                seen=seen,
                primary_ids=primary_ids,
                half=half,
                fallback_window=fallback_window,
            )
            for member in members:
                seen.add(member.id)
            grouped_members.append((primary, members))

        all_fragments: list[Fragment] = list(primaries)
        for _, members in grouped_members:
            all_fragments.extend(members)
        responses_by_id = await self._build_fragment_response_map(
            fragments=all_fragments,
            database_session=database_session,
        )

        groups: list[FragmentSectionGroup] = []
        for primary, members in grouped_members:
            primary_response = responses_by_id.get(primary.id)
            if primary_response is None:
                continue
            groups.append(
                FragmentSectionGroup(
                    primary=primary_response,
                    section_fragments=[
                        responses_by_id[m.id] for m in members if m.id in responses_by_id
                    ],
                )
            )

        primary_responses = [
            responses_by_id[p.id] for p in primaries if p.id in responses_by_id
        ]
        return FragmentListResponse(fragments=primary_responses, groups=groups)

    @staticmethod
    def _select_section_members(
            *,
            primary: Fragment,
            pool: list[Fragment],
            seen: set[int],
            primary_ids: set[int],
            half: int,
            fallback_window: int,
    ) -> list[Fragment]:
        window = half if primary.section_path is not None else fallback_window
        members: list[Fragment] = []
        for candidate in pool:
            if candidate.id in seen or candidate.id in primary_ids:
                continue
            if candidate.document_id != primary.document_id:
                continue
            if primary.section_path is not None and candidate.section_path != primary.section_path:
                continue
            if abs(int(candidate.fragment_index) - int(primary.fragment_index)) > window:
                continue
            members.append(candidate)
        members.sort(key=lambda f: int(f.fragment_index))
        return members

    async def _build_fragment_response_map(
            self,
            fragments: list[Fragment],
            database_session: AsyncSession,
    ) -> dict[int, FragmentResponse]:
        if not fragments:
            return {}

        unique: dict[int, Fragment] = {}
        for fragment in fragments:
            unique.setdefault(fragment.id, fragment)

        document_ids = list({f.document_id for f in unique.values()})
        documents = await self._document_repository.get_documents_by_ids(
            document_ids=document_ids,
            database_session=database_session,
        )
        docs_by_id = {doc.id: doc for doc in documents}
        responses = self._assemble_fragment_responses(
            fragments=list(unique.values()),
            docs_by_id=docs_by_id,
        )
        return {response.id: response for response in responses}

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
                        "contextualized_content": fragment.contextualized_content,
                        "fragment_index": fragment.fragment_index,
                        "page_number": fragment.page_number,
                        "section_path": fragment.section_path,
                        "heading": fragment.heading,
                        "char_start": fragment.char_start,
                        "char_end": fragment.char_end,
                        "bbox": fragment.bbox,
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
            representation: Literal["raw", "contextual"] = "raw",
    ) -> list[Fragment]:
        try:
            fragments = await self._fragment_repository.get_most_similar_fragments(
                query_vector=query_vector,
                database_session=database_session,
                embedding_identity=self._embedder_factory.get_active_embedding_identity(),
                k=k,
                threshold=self._settings.similarity_threshold,
                document_ids=document_ids,
                representation=representation,
            )
            logger.debug(
                "Similar fragments retrieved.",
                extra={"fragment_count": len(fragments), "representation": representation},
            )
            return fragments
        except Exception as e:
            raise FragmentQueryRetrievalException("Failed to retrieve similar fragments.") from e

    async def _retrieve_bm25_fragments(
            self,
            database_session: AsyncSession,
            query_text: str,
            k: int,
            document_ids: list[int] | None = None,
            representation: Literal["raw", "contextual"] = "raw",
    ) -> list[Fragment]:
        try:
            return await self._fragment_repository.get_most_relevant_fragments_bm25(
                query=query_text,
                database_session=database_session,
                k=k,
                min_score=self._settings.bm25_min_score,
                query_max_chars=self._settings.bm25_query_max_chars,
                document_ids=document_ids,
                representation=representation,
            )
        except Exception as e:
            raise FragmentQueryRetrievalException("Failed to retrieve BM25-ranked fragments.") from e

    async def _retrieve_similar_isolated(
            self,
            *,
            query_vector: list[float],
            k: int,
            document_ids: list[int] | None,
            semaphore: asyncio.Semaphore,
            representation: Literal["raw", "contextual"] = "raw",
    ) -> list[Fragment]:
        async with semaphore:
            async with self._database_manager.session() as session:
                return await self._retrieve_similar_fragments(
                    database_session=session,
                    query_vector=query_vector,
                    k=k,
                    document_ids=document_ids,
                    representation=representation,
                )

    async def _retrieve_bm25_isolated(
            self,
            *,
            query_text: str,
            k: int,
            document_ids: list[int] | None,
            semaphore: asyncio.Semaphore,
            representation: Literal["raw", "contextual"] = "raw",
    ) -> list[Fragment]:
        async with semaphore:
            async with self._database_manager.session() as session:
                return await self._retrieve_bm25_fragments(
                    database_session=session,
                    query_text=query_text,
                    k=k,
                    document_ids=document_ids,
                    representation=representation,
                )

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
