import logging
from typing import Optional

from app.application.services.document_question_service.document_question_state import DocumentQuestionState
from app.application.services.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
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


def _build_question_context_fragments_request(
        state: DocumentQuestionState,
        settings: DocumentQuestionServiceSettings,
) -> QuestionContextFragmentsRequest:
    original = state.current_message.content.strip()
    sf = settings.semantic_fragments_per_lane
    bf = settings.bm25_fragments_per_lane

    semantic_queries: list[SemanticQuery] = [
        SemanticQuery(text=original, max_fragments=sf),
    ]

    base = (state.base_question or "").strip()
    if state.history_messages and base and base != original:
        semantic_queries.append(SemanticQuery(text=base, max_fragments=sf))

    if settings.use_keywords:
        kw = (state.keyword_question or "").strip()
        if kw:
            semantic_queries.append(SemanticQuery(text=kw, max_fragments=sf))

    bm25_queries: list[BM25Query] = []
    enable_bm25 = settings.enable_dual_bm25 and (
            bool(state.history_messages)
            or (base and base != original)
    )
    if enable_bm25:
        bm25_queries.append(BM25Query(text=original, max_fragments=bf))
        if base:
            bm25_queries.append(BM25Query(text=base, max_fragments=bf))

    pool = (
            sum(q.max_fragments for q in semantic_queries)
            + sum(q.max_fragments for q in bm25_queries)
    )
    rerank = RerankConfig(enabled=False)
    if settings.use_rerank and settings.rerank_max_fragments is not None and pool > 0:
        effective = min(settings.rerank_max_fragments, pool)
        if effective >= 1:
            rerank = RerankConfig(enabled=True, max_fragments=effective)

    return QuestionContextFragmentsRequest(
        chat_id=state.chat_id,
        semantic_queries=semantic_queries,
        bm25_queries=bm25_queries,
        rerank=rerank,
    )


class ContextDocumentQuestionProcessor:
    def __init__(
            self,
            document_question_service_settings: DocumentQuestionServiceSettings,
            document_context_provider: DocumentContextProviderInterface,
    ) -> None:
        self._settings = document_question_service_settings
        self._document_context_provider = document_context_provider

    async def run(self, document_question_state: DocumentQuestionState) -> None:
        keyword_question: Optional[str] = None
        if self._settings.use_keywords and document_question_state.keyword_question:
            keyword_question = document_question_state.keyword_question

        try:
            request = _build_question_context_fragments_request(
                state=document_question_state,
                settings=self._settings,
            )
            fragments = await self._document_context_provider.retrieve_context_fragments_by_question_request(
                authenticated_user=document_question_state.authenticated_user,
                request=request,
            )
            document_question_state.fragments = fragments.fragments
            logger.debug(
                "Context fragments retrieved",
                extra={
                    "fragment_count": len(fragments.fragments),
                    "semantic_queries": len(request.semantic_queries),
                    "bm25_queries": len(request.bm25_queries),
                    "use_rerank": request.rerank.enabled,
                    "has_keywords": bool(keyword_question),
                },
            )
        except DocumentQuestionServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to retrieve context fragments",
                extra={
                    "error_type": type(e).__name__,
                },
            )
            raise DocumentQuestionServiceException(
                "Error retrieving context fragments from the document service"
            ) from e
