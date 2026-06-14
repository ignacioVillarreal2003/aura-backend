import logging
from typing import Any, Dict, List, Optional

from app.application.services.user_interactions.rag_agent_service.context_formatting import build_document_context
from app.application.services.user_interactions.rag_agent_service.interfaces.rag_node_interface import RagNodeInterface
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import RagAgentServiceSettings
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


class ContextRetrieverNode(RagNodeInterface):
    def __init__(
            self,
            document_context_provider: DocumentContextProviderInterface,
            settings: RagAgentServiceSettings,
    ) -> None:
        self._provider = document_context_provider
        self._settings = settings
        logger.debug("ContextRetrieverNode initialized")

    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        logger.debug("Processing context retriever")

        query: str = state.get("query", "")
        keywords: List[str] = state.get("keywords", [])
        authenticated_user: AuthenticatedUser = state["authenticated_user"]

        if not query:
            logger.warning("No query available for retrieval")
            return {"retrieved_fragments": [], "context": ""}

        try:
            fragments = await self._retrieve(authenticated_user, query, keywords)
            context = build_document_context(fragments, self._settings.max_context_chars)
            logger.info(
                "Context retrieved",
                extra={"fragments_count": len(fragments), "context_chars": len(context)},
            )
            return {"retrieved_fragments": fragments, "context": context}
        except Exception:
            logger.error("Context retrieval failed — returning empty context", exc_info=True)
            return {"retrieved_fragments": [], "context": ""}

    async def _retrieve(
            self,
            authenticated_user: AuthenticatedUser,
            query: str,
            keywords: List[str],
    ) -> List[FragmentResponse]:
        keywords_str = self._build_keywords_string(keywords)

        semantic_queries = [SemanticQuery(text=query, max_fragments=self._settings.max_fragments)]
        bm25_queries = (
            [BM25Query(text=keywords_str, max_fragments=self._settings.bm25_fragments)]
            if keywords_str
            else []
        )

        pool = sum(q.max_fragments for q in semantic_queries) + sum(q.max_fragments for q in bm25_queries)
        if self._settings.use_rerank and pool > 0:
            effective = min(self._settings.rerank_max_fragments, pool)
            rerank = RerankConfig(enabled=True, max_fragments=effective)
        else:
            rerank = RerankConfig(enabled=False)

        request = QuestionContextFragmentsRequest(
            semantic_queries=semantic_queries,
            bm25_queries=bm25_queries,
            rerank=rerank,
            adjacent_chunks=self._settings.adjacent_chunks,
        )
        response = await self._provider.retrieve_context_fragments_by_question_request(
            authenticated_user=authenticated_user,
            request=request,
        )
        return response.fragments

    @staticmethod
    def _build_keywords_string(keywords: List[str]) -> Optional[str]:
        if not keywords:
            return None
        joined = " ".join(keywords)
        return joined[:16_000] if joined else None
