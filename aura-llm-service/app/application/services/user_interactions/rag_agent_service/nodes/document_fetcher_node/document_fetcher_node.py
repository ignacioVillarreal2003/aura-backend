import logging
from typing import Any, Dict, List

from app.application.services.user_interactions.rag_agent_service.constants.rag_node_name import RagNodeName
from app.application.services.user_interactions.rag_agent_service.context_formatting import build_document_context
from app.application.services.user_interactions.rag_agent_service.interfaces.rag_node_interface import RagNodeInterface
from app.application.services.user_interactions.rag_agent_service.node_failures import EXPECTED_RETRIEVAL_ERRORS
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import RagAgentServiceSettings
from app.configuration.metrics import record_rag_node_failure
from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
from app.infrastructure.http.document_context_provider.dtos.question_context_fragments_request import (
    BM25Query,
    QuestionContextFragmentsRequest,
    RerankConfig,
    SemanticQuery,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)

logger = logging.getLogger(__name__)


class DocumentFetcherNode(RagNodeInterface):
    def __init__(
            self,
            document_context_provider: DocumentContextProviderInterface,
            settings: RagAgentServiceSettings,
    ) -> None:
        self._provider = document_context_provider
        self._settings = settings
        logger.debug("DocumentFetcherNode initialized")

    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        logger.debug("Processing document fetcher")

        query: str = state.get("query", "")
        keywords: List[str] = state.get("keywords", [])
        authenticated_user: AuthenticatedUser = state["authenticated_user"]

        existing: List[FragmentResponse] = list(state.get("retrieved_fragments") or [])

        if not query:
            logger.warning("No query available for document fetcher")
            return {"retrieved_fragments": existing, "context": state.get("context", "")}

        try:
            fetched = await self._fetch(authenticated_user, query, keywords)
            combined = self._merge_fragments(existing, fetched)
            context = build_document_context(combined, self._settings.max_context_chars)
            logger.info(
                "Documents fetched",
                extra={
                    "fragments_count": len(fetched),
                    "documents_count": len({f.document_id for f in fetched}),
                    "merged_total": len(combined),
                },
            )
            return {"retrieved_fragments": combined, "context": context}
        except EXPECTED_RETRIEVAL_ERRORS as exc:
            record_rag_node_failure(RagNodeName.document_fetcher.value, "expected", exc)
            logger.warning(
                "Document fetch degraded (expected error) — keeping existing context",
                exc_info=True,
            )
            return {"retrieved_fragments": existing, "context": state.get("context", "")}
        except Exception as exc:
            record_rag_node_failure(RagNodeName.document_fetcher.value, "unexpected", exc)
            logger.exception("Document fetch failed with an unexpected error")
            raise

    @staticmethod
    def _merge_fragments(
            existing: List[FragmentResponse],
            new: List[FragmentResponse],
    ) -> List[FragmentResponse]:
        seen: set[int] = {f.id for f in existing}
        merged = list(existing)
        for fragment in new:
            if fragment.id not in seen:
                seen.add(fragment.id)
                merged.append(fragment)
        return merged

    async def _fetch(
            self,
            authenticated_user: AuthenticatedUser,
            query: str,
            keywords: List[str],
    ) -> List[FragmentResponse]:
        discovered = await self._discover(authenticated_user, query, keywords)
        if not discovered:
            return []

        doc_ids = self._top_document_ids(discovered)
        full_response = await self._provider.retrieve_context_fragments_by_document(
            authenticated_user=authenticated_user,
            document_ids=doc_ids,
        )
        return full_response.fragments

    async def _discover(
            self,
            authenticated_user: AuthenticatedUser,
            query: str,
            keywords: List[str],
    ) -> List[FragmentResponse]:
        semantic_queries = [SemanticQuery(text=query, max_fragments=self._settings.max_fragments)]
        keywords_str = " ".join(keywords).strip()
        bm25_queries = (
            [BM25Query(text=keywords_str, max_fragments=self._settings.bm25_fragments)]
            if keywords_str
            else []
        )

        pool = sum(q.max_fragments for q in semantic_queries) + sum(q.max_fragments for q in bm25_queries)
        if self._settings.use_rerank and pool > 0:
            rerank = RerankConfig(enabled=True, max_fragments=min(self._settings.rerank_max_fragments, pool))
        else:
            rerank = RerankConfig(enabled=False)

        request = QuestionContextFragmentsRequest(
            semantic_queries=semantic_queries,
            bm25_queries=bm25_queries,
            rerank=rerank,
            adjacent_chunks=0,
        )
        response = await self._provider.retrieve_context_fragments_by_question_request(
            authenticated_user=authenticated_user,
            request=request,
        )
        return response.fragments

    def _top_document_ids(self, fragments: List[FragmentResponse]) -> List[int]:
        seen: set[int] = set()
        doc_ids: List[int] = []
        for fragment in fragments:
            if fragment.document_id not in seen:
                seen.add(fragment.document_id)
                doc_ids.append(fragment.document_id)
            if len(doc_ids) >= self._settings.document_fetcher_max_documents:
                break
        return doc_ids
