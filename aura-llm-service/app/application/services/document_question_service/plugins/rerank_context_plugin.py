from __future__ import annotations

import logging
from threading import Lock
from typing import ClassVar

from sentence_transformers import CrossEncoder
from app.application.services.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)

logger = logging.getLogger(__name__)


class RerankContextPlugin(DocumentQuestionPlugin):
    _MODEL_CACHE: ClassVar[dict[str, CrossEncoder]] = {}
    _MODEL_LOCK: ClassVar[Lock] = Lock()

    @property
    def plugin_name(self) -> str:
        return "rerank_context"

    def should_run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> bool:
        return len(state.retrieved_fragments) > resources.settings.rerank_threshold

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        query = state.effective_query or state.current_message.content
        fragments = state.retrieved_fragments
        if not fragments:
            return

        top_n = resources.settings.max_reranked_fragments
        model_name = resources.settings.rerank_model_name
        min_score = resources.settings.rerank_min_score
        batch_size = resources.settings.rerank_batch_size

        logger.debug(
            "Running cross-encoder reranking",
            extra={
                "model_name": model_name,
                "total_fragments": len(fragments),
                "max_reranked": top_n,
                "min_score": min_score,
            },
        )

        try:
            model = self._get_or_create_model(model_name)
            pairs = [(query, fragment) for fragment in fragments]
            scores = model.predict(
                pairs,
                batch_size=batch_size,
                show_progress_bar=False,
            )

            ranked = sorted(
                zip(scores, fragments),
                key=lambda item: float(item[0]),
                reverse=True,
            )
            top_ranked = ranked[:top_n]
            selected = [
                fragment
                for score, fragment in top_ranked
                if float(score) >= min_score
            ]

            if not selected:
                logger.warning(
                    "Reranking returned no fragments above threshold, using top-k",
                    extra={"top_n": top_n, "min_score": min_score},
                )
                selected = [fragment for _, fragment in top_ranked]

            logger.debug(
                "Cross-encoder reranking complete",
                extra={
                    "kept": len(selected),
                    "scores": [round(float(score), 3) for score, _ in top_ranked],
                },
            )
            state.retrieved_fragments = selected
        except Exception:
            logger.warning(
                "Cross-encoder reranking failed, falling back to original top-k order",
                exc_info=True,
            )
            state.retrieved_fragments = fragments[:top_n]

    @classmethod
    def _get_or_create_model(cls, model_name: str) -> CrossEncoder:
        with cls._MODEL_LOCK:
            model = cls._MODEL_CACHE.get(model_name)
            if model is None:
                logger.info(
                    "Loading cross-encoder reranker model",
                    extra={"model_name": model_name},
                )
                model = CrossEncoder(model_name)
                cls._MODEL_CACHE[model_name] = model
            return model
