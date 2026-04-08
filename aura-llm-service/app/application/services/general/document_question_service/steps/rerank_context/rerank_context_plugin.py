import asyncio
import logging
import time
from functools import partial
from threading import Lock
from typing import ClassVar, Optional
from sentence_transformers import CrossEncoder

from app.application.services.general.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)
from app.application.services.general.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.general.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.general.document_question_service.steps.rerank_context.rerank_context_settings import (
    RerankContextSettings,
)
from app.infrastructure.http.document_context_provider.dtos.fragment_response import (
    FragmentResponse,
)

logger = logging.getLogger(__name__)


class RerankContextPlugin(DocumentQuestionPlugin):
    def __init__(self, rerank_context_settings: Optional[RerankContextSettings] = None) -> None:
        self._settings = rerank_context_settings or RerankContextSettings()

    _model: ClassVar[Optional[CrossEncoder]] = None
    _model_lock: ClassVar[Lock] = Lock()

    @classmethod
    def _get_or_load_model(cls, settings: RerankContextSettings) -> CrossEncoder:
        with cls._model_lock:
            if cls._model is None:
                logger.info(
                    "Loading cross-encoder reranker model",
                    extra={"model_name": settings.model_name, "device": settings.device},
                )
                t0 = time.monotonic()
                kwargs = {}
                if settings.device is not None:
                    kwargs["device"] = settings.device
                cls._model = CrossEncoder(settings.model_name, **kwargs)
                elapsed = time.monotonic() - t0
                logger.info(
                    "Cross-encoder model loaded",
                    extra={"model_name": settings.model_name, "load_time_s": round(elapsed, 2)},
                )
            return cls._model

    @property
    def plugin_name(self) -> str:
        return "rerank_context"

    def should_run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> bool:
        return len(state.retrieved_fragments) >= self._settings.threshold

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        query = state.retrieval_query or state.current_message.content
        fragments: list[FragmentResponse] = state.retrieved_fragments

        if not fragments:
            return

        logger.debug(
            "Running cross-encoder reranking",
            extra={
                "model_name": self._settings.model_name,
                "total_fragments": len(fragments),
                "top_n": self._settings.top_n,
                "min_score": self._settings.min_score,
            },
        )

        try:
            model = self._get_or_load_model(self._settings)
            pairs = [(query, fragment.content) for fragment in fragments]

            loop = asyncio.get_running_loop()
            predict_fn = partial(
                model.predict,
                pairs,
                batch_size=self._settings.batch_size,
                show_progress_bar=False,
            )
            scores = await loop.run_in_executor(None, predict_fn)

            ranked: list[tuple[float, FragmentResponse]] = sorted(
                zip(scores, fragments),
                key=lambda item: float(item[0]),
                reverse=True,
            )
            top_ranked = ranked[:self._settings.top_n]

            selected = [
                fragment
                for score, fragment in top_ranked
                if float(score) >= self._settings.min_score
            ]

            if not selected:
                logger.warning(
                    "No fragments above min_score threshold, using top-k without score filter",
                    extra={"top_n": self._settings.top_n, "min_score": self._settings.min_score},
                )
                selected = [fragment for _, fragment in top_ranked]

            logger.debug(
                "Cross-encoder reranking complete",
                extra={
                    "kept": len(selected),
                    "scores": [round(float(s), 3) for s, _ in top_ranked],
                },
            )
            state.rerank_fragments = selected

        except Exception:
            logger.warning(
                "Cross-encoder reranking failed, falling back to original top-k order",
                exc_info=True,
            )
            state.rerank_fragments = fragments[:self._settings.top_n]
