import asyncio
import logging
import time
from functools import partial
from threading import Lock
from typing import Any, ClassVar, Optional

from sentence_transformers import CrossEncoder

from app.application.services.fragment.fragment_query_service.fragment_query_service_settings import (
    FragmentQueryServiceSettings,
)

logger = logging.getLogger(__name__)


class FragmentContextReranker:
    """Cross-encoder reranking for retrieved fragments (lazy-loaded model, process-wide singleton)."""

    _model: ClassVar[Optional[CrossEncoder]] = None
    _model_lock: ClassVar[Lock] = Lock()

    def __init__(self, fragment_query_service_settings: FragmentQueryServiceSettings) -> None:
        self._settings = fragment_query_service_settings

    @classmethod
    def _get_or_load_model(cls, settings: FragmentQueryServiceSettings) -> CrossEncoder:
        with cls._model_lock:
            if cls._model is None:
                logger.info(
                    "Loading cross-encoder reranker model",
                    extra={"model_name": settings.rerank_model_name, "device": settings.rerank_device},
                )
                t0 = time.monotonic()
                kwargs: dict[str, Any] = {}
                if settings.rerank_device is not None:
                    kwargs["device"] = settings.rerank_device
                cls._model = CrossEncoder(settings.rerank_model_name, **kwargs)
                elapsed = time.monotonic() - t0
                logger.info(
                    "Cross-encoder model loaded",
                    extra={"model_name": settings.rerank_model_name, "load_time_s": round(elapsed, 2)},
                )
            return cls._model

    async def rerank_fragments(
            self,
            query: str,
            fragments: list[Any],
            top_n: int,
    ) -> list[Any]:
        if not fragments:
            return []

        logger.debug(
            "Running cross-encoder reranking",
            extra={
                "model_name": self._settings.rerank_model_name,
                "total_fragments": len(fragments),
                "top_n": top_n,
                "min_score": self._settings.rerank_min_score,
            },
        )

        try:
            model = self._get_or_load_model(self._settings)
            pairs = [(query, fragment.content) for fragment in fragments]

            loop = asyncio.get_running_loop()
            predict_fn = partial(
                model.predict,
                pairs,
                batch_size=self._settings.rerank_batch_size,
                show_progress_bar=False,
            )
            scores = await loop.run_in_executor(None, predict_fn)

            ranked: list[tuple[float, Any]] = sorted(
                zip(scores, fragments),
                key=lambda item: float(item[0]),
                reverse=True,
            )
            top_ranked = ranked[:top_n]

            selected = [
                fragment
                for score, fragment in top_ranked
                if float(score) >= self._settings.rerank_min_score
            ]

            if not selected:
                logger.warning(
                    "No fragments above min_score threshold, using top-k without score filter",
                    extra={"top_n": top_n, "min_score": self._settings.rerank_min_score},
                )
                selected = [fragment for _, fragment in top_ranked]

            logger.debug(
                "Cross-encoder reranking complete",
                extra={
                    "kept": len(selected),
                    "scores": [round(float(s), 3) for s, _ in top_ranked],
                },
            )
            return selected

        except Exception:
            logger.warning(
                "Cross-encoder reranking failed, falling back to original top-k order",
                exc_info=True,
            )
            return fragments[:top_n]
