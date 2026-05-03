import asyncio
import logging
import time
from functools import partial
from typing import Any, ClassVar, Optional
from sentence_transformers import CrossEncoder

from app.application.services.fragment.fragment_query_service.fragment_query_service_settings import (
    FragmentQueryServiceSettings,
)
from app.infrastructure.persistence.database.orm.fragment import Fragment

logger = logging.getLogger(__name__)


class FragmentReranker:
    _model: ClassVar[Optional[CrossEncoder]] = None
    _model_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, fragment_query_service_settings: FragmentQueryServiceSettings) -> None:
        self._settings = fragment_query_service_settings

    @classmethod
    async def _get_or_load_model(cls, settings: FragmentQueryServiceSettings) -> CrossEncoder:
        async with cls._model_lock:
            if cls._model is None:
                logger.info(
                    "Loading cross-encoder reranker model",
                    extra={"model_name": settings.rerank_model_name, "device": settings.rerank_device},
                )
                t0 = time.monotonic()

                def _load() -> CrossEncoder:
                    kwargs: dict[str, Any] = {}
                    if settings.rerank_device is not None:
                        kwargs["device"] = settings.rerank_device
                    return CrossEncoder(settings.rerank_model_name, **kwargs)

                loop = asyncio.get_running_loop()
                cls._model = await loop.run_in_executor(None, _load)
                elapsed = time.monotonic() - t0
                logger.info(
                    "Cross-encoder model loaded",
                    extra={"model_name": settings.rerank_model_name, "load_time_s": round(elapsed, 2)},
                )
            return cls._model

    @classmethod
    async def reset_model(cls) -> None:
        async with cls._model_lock:
            cls._model = None

    async def rerank_fragments(
        self,
        query: str,
        fragments: list[Fragment],
        top_n: int,
    ) -> list[Fragment]:
        if not fragments:
            return []

        if top_n <= 0:
            raise ValueError(f"top_n must be a positive integer, got {top_n}.")

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
            model = await self._get_or_load_model(self._settings)
            pairs = [(query, fragment.content) for fragment in fragments]

            loop = asyncio.get_running_loop()
            predict_fn = partial(
                model.predict,
                pairs,
                batch_size=self._settings.rerank_batch_size,
                show_progress_bar=False,
            )
            scores = await loop.run_in_executor(None, predict_fn)

            ranked: list[tuple[float, Fragment]] = sorted(
                zip(scores, fragments, strict=True),
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

        except (MemoryError, SystemExit, KeyboardInterrupt):
            raise
        except Exception:
            logger.warning(
                "Cross-encoder reranking failed, falling back to original top-k order",
                exc_info=True,
            )
            return fragments[:top_n]