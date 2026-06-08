import logging

from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.generation_state import GenerationState
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

_MAX_QUERY_CHARS = 400


class ContextRetrievalProcessor:
    def __init__(
            self,
            settings: GenerationSettings,
            document_context_provider: DocumentContextProviderInterface,
    ) -> None:
        self._settings = settings
        self._document_context_provider = document_context_provider

    async def run(self, state: GenerationState, rag_queries: list[str]) -> None:
        request = self._build_request(state, rag_queries)
        try:
            result = await self._document_context_provider.retrieve_context_fragments_by_question_request(
                authenticated_user=state.authenticated_user,
                request=request,
            )
            state.fragments = result.fragments[:self._settings.max_rag_fragments]
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
            rag_queries: list[str],
    ) -> QuestionContextFragmentsRequest:
        settings = self._settings
        effective = (state.base_question or state.current_message.content).strip()[:_MAX_QUERY_CHARS]
        keywords = (state.keyword_question or "").strip()

        sf = settings.semantic_fragments_per_lane
        bf = settings.bm25_fragments_per_lane

        semantic_queries: list[SemanticQuery] = [
            SemanticQuery(text=f"{effective} {q}".strip(), max_fragments=sf)
            for q in rag_queries
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
        if settings.use_rerank and pool > 0:
            rerank = RerankConfig(enabled=True, max_fragments=min(settings.max_rag_fragments, pool))

        return QuestionContextFragmentsRequest(
            chat_id=state.chat_id,
            semantic_queries=semantic_queries,
            bm25_queries=bm25_queries,
            rerank=rerank,
            adjacent_chunks=settings.adjacent_chunks,
        )
