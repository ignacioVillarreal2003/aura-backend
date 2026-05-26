import logging
from typing import Any, Dict, List, Optional

from app.application.services.agent_service.agent_settings import AgentServiceSettings
from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.interfaces.node_interface import NodeInterface
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


class RetrieverNode(NodeInterface):
    def __init__(
            self,
            document_context_provider: DocumentContextProviderInterface,
            settings: AgentServiceSettings,
    ) -> None:
        self._provider = document_context_provider
        self._settings = settings
        logger.debug("RetrieverNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing retriever")

        resolved_query = agent_state.get("resolved_query", "") or agent_state.get("normalized_query", "")
        keywords: List[str] = agent_state.get("keywords", [])
        authenticated_user: AuthenticatedUser = agent_state["authenticated_user"]

        if not resolved_query:
            logger.warning("No query available for retrieval")
            return {"retrieved_fragments": []}

        try:
            fragments = await self._retrieve(authenticated_user, resolved_query, keywords)
            logger.info("Retrieval completed", extra={"fragments_count": len(fragments)})
            return {"retrieved_fragments": fragments}

        except Exception:
            logger.error("Retrieval failed — returning empty fragment list", exc_info=True)
            return {"retrieved_fragments": []}

    async def _retrieve(
            self,
            authenticated_user: AuthenticatedUser,
            query: str,
            keywords: List[str],
    ) -> List[FragmentResponse]:
        keywords_str = self._build_keywords_string(keywords)

        semantic_queries = [SemanticQuery(text=query, max_fragments=self._settings.max_vector_fragments)]
        bm25_queries = (
            [BM25Query(text=keywords_str, max_fragments=self._settings.max_keyword_fragments)]
            if keywords_str
            else []
        )

        pool = sum(q.max_fragments for q in semantic_queries) + sum(q.max_fragments for q in bm25_queries)
        effective_rerank = min(self._settings.max_rerank_fragments, pool)
        rerank = RerankConfig(enabled=True, max_fragments=effective_rerank)

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
