import logging
from typing import Optional

from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.processors.context_retrieval_processor.context_retrieval_settings import (
    ContextRetrievalSettings,
)
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


class ContextRetrievalProcessor:
    def __init__(
            self,
            document_context_provider: DocumentContextProviderInterface,
            context_retrieval_settings: Optional[ContextRetrievalSettings] = None,
    ) -> None:
        self._settings = context_retrieval_settings or ContextRetrievalSettings()
        self._document_context_provider = document_context_provider

    async def run(self, state: GenerationState, queries: list[str]) -> None:
        request = self._build_request(state, queries)
        try:
            result = await self._document_context_provider.retrieve_context_fragments_by_question_request(
                authenticated_user=state.authenticated_user,
                request=request,
            )
            state.fragments = result.fragments[:self._settings.max_fragments]
            logger.debug(
                "Context fragments retrieved",
                extra={
                    "fragment_count": len(state.fragments),
                    "semantic_queries": len(request.semantic_queries),
                    "bm25_queries": len(request.bm25_queries),
                    "use_rerank": request.rerank.enabled,
                },
            )
        except Exception:
            logger.warning(
                "Fragment retrieval failed; proceeding without context",
                extra={"user_id": state.authenticated_user.id},
                exc_info=True,
            )
            state.fragments = []

    def _build_request(
            self,
            state: GenerationState,
            queries: list[str],
    ) -> QuestionContextFragmentsRequest:
        effective = (state.base_question or state.current_message.content).strip()
        keywords = (state.keyword_question or "").strip()

        sf = self._settings.semantic_fragments_per_lane
        bf = self._settings.bm25_fragments_per_lane

        semantic_queries: list[SemanticQuery] = [
            SemanticQuery(text=f"{effective} {q}".strip(), max_fragments=sf)
            for q in queries
        ]
        if keywords:
            semantic_queries.append(SemanticQuery(text=keywords, max_fragments=sf))

        bm25_queries: list[BM25Query] = [BM25Query(text=effective, max_fragments=bf)]
        if keywords and keywords != effective:
            bm25_queries.append(BM25Query(text=keywords, max_fragments=bf))

        pool = (
                sum(q.max_fragments for q in semantic_queries)
                + sum(q.max_fragments for q in bm25_queries)
        )
        rerank = RerankConfig(enabled=False)
        if self._settings.use_rerank and pool > 0:
            rerank = RerankConfig(enabled=True, max_fragments=min(self._settings.max_fragments, pool))

        return QuestionContextFragmentsRequest(
            chat_id=state.chat_id,
            semantic_queries=semantic_queries,
            bm25_queries=bm25_queries,
            rerank=rerank,
            adjacent_chunks=self._settings.adjacent_chunks,
        )
