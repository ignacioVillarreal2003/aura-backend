import logging
from typing import Optional

from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.processors.context_retrieval_processor.context_retrieval_settings import (
    ContextRetrievalSettings,
)
from app.application.services.generation_shared.processors.processor_observability import (
    log_extra,
    retrieval_failures_total,
    retrieval_fragments_returned,
    retrieval_total,
    timed,
)
from app.configuration.tracing import retrieval_span
from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.infrastructure.http.document_context_provider.dtos.question_context_fragments_request import (
    BM25Query,
    QuestionContextFragmentsRequest,
    RerankConfig,
    SemanticQuery,
)
from app.infrastructure.http.document_context_provider.exceptions.document_context_provider_exception import (
    DocumentContextProviderTimeoutException,
    DocumentContextProviderUnauthorizedException,
    DocumentContextProviderUnavailableException,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)

logger = logging.getLogger(__name__)

_STAGE = "context_retrieval"


def _failure_reason(error: Exception) -> str:
    if isinstance(error, DocumentContextProviderTimeoutException):
        return "timeout"
    if isinstance(error, DocumentContextProviderUnavailableException):
        return "unavailable"
    if isinstance(error, DocumentContextProviderUnauthorizedException):
        return "unauthorized"
    return "unknown"


class ContextRetrievalProcessor:
    def __init__(
            self,
            document_context_provider: DocumentContextProviderInterface,
            context_retrieval_settings: Optional[ContextRetrievalSettings] = None,
    ) -> None:
        self._settings = context_retrieval_settings or ContextRetrievalSettings()
        self._document_context_provider = document_context_provider

    async def run(self, state: GenerationState) -> None:
        request = self._build_request(state)
        lane_texts = [q.text for q in request.semantic_queries]

        with timed(_STAGE), retrieval_span(_STAGE, lane_texts):
            try:
                result = await self._document_context_provider.retrieve_context_fragments_by_question_request(
                    authenticated_user=state.authenticated_user,
                    request=request,
                )
            except Exception as error:
                reason = _failure_reason(error)
                retrieval_total.labels(outcome="failure").inc()
                retrieval_failures_total.labels(reason=reason).inc()
                state.retrieval_degraded = True
                state.fragments = []
                logger.warning(
                    "Fragment retrieval failed; proceeding without context.",
                    extra=log_extra(reason=reason, user_id=state.authenticated_user.id),
                    exc_info=True,
                )
                return

            returned = len(result.fragments)
            fragments = result.fragments[:self._settings.max_fragments]
            fragments = self._apply_char_budget(fragments)
            state.fragments = fragments
            state.section_groups = getattr(result, "groups", None) or None

            retrieval_fragments_returned.observe(len(fragments))
            retrieval_total.labels(outcome="success" if fragments else "empty").inc()
            logger.info(
                "Context fragments retrieved.",
                extra=log_extra(
                    user_id=state.authenticated_user.id,
                    lanes_semantic=len(request.semantic_queries),
                    lanes_bm25=len(request.bm25_queries),
                    fragments_returned=returned,
                    fragments_kept=len(fragments),
                    rerank=request.rerank.enabled,
                ),
            )

    def _apply_char_budget(self, fragments: list[FragmentResponse]) -> list[FragmentResponse]:
        budget = self._settings.max_context_chars
        if budget is None:
            return fragments
        selected: list[FragmentResponse] = []
        used = 0
        for fragment in fragments:
            length = len(fragment.effective_content or "")
            if selected and used + length > budget:
                break
            selected.append(fragment)
            used += length
        return selected

    def _build_request(self, state: GenerationState) -> QuestionContextFragmentsRequest:
        query_texts = self._unique_query_texts(
            original=state.current_message.content.strip(),
            base=(state.base_question or "").strip(),
            keywords=(state.keyword_question or "").strip(),
        )

        sf = self._settings.semantic_fragments_per_lane
        bf = self._settings.bm25_fragments_per_lane
        semantic_queries = [SemanticQuery(text=text, max_fragments=sf) for text in query_texts]
        bm25_queries = [BM25Query(text=text, max_fragments=bf) for text in query_texts]

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
            context_expansion=self._settings.context_expansion,
        )

    @staticmethod
    def _unique_query_texts(original: str, base: str, keywords: str) -> list[str]:
        texts: list[str] = []
        for candidate in (original, base, keywords):
            if candidate and candidate not in texts:
                texts.append(candidate)
        return texts
