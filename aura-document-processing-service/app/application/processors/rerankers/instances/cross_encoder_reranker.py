import asyncio
import logging
import time
from functools import partial
from typing import Any, ClassVar, Optional
from sentence_transformers import CrossEncoder

from app.application.processors.rerankers.exceptions.reranker_exception import (
    RerankerInitializationException,
    RerankerExecutionException,
)
from app.application.processors.rerankers.interfaces.reranker_interface import RerankerInterface
from app.application.processors.rerankers.reranker_settings import RerankerSettings

logger = logging.getLogger(__name__)


class CrossEncoderReranker(RerankerInterface):
    _model: ClassVar[Optional[CrossEncoder]] = None
    _model_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    def __init__(self, reranker_settings: RerankerSettings) -> None:
        self._settings = reranker_settings
        logger.info(
            "The cross-encoder reranker was initialized.",
            extra={
                "model_name": self._settings.model_name,
                "device": self._settings.device,
                "min_score": self._settings.min_score,
                "batch_size": self._settings.batch_size,
            },
        )

    @classmethod
    async def _get_or_load_model(cls, settings: RerankerSettings) -> CrossEncoder:
        async with cls._model_lock:
            if cls._model is None:
                logger.info(
                    "Loading cross-encoder reranker model.",
                    extra={"model_name": settings.model_name, "device": settings.device},
                )
                t0 = time.monotonic()

                def _load() -> CrossEncoder:
                    kwargs: dict[str, Any] = {}
                    if settings.device is not None:
                        kwargs["device"] = settings.device
                    return CrossEncoder(settings.model_name, **kwargs)

                try:
                    loop = asyncio.get_running_loop()
                    cls._model = await loop.run_in_executor(None, _load)
                except Exception as e:
                    logger.exception("Failed to load the cross-encoder model.")
                    raise RerankerInitializationException(
                        "Failed to load the cross-encoder reranker model."
                    ) from e

                elapsed = time.monotonic() - t0
                logger.info(
                    "Cross-encoder model loaded successfully.",
                    extra={"model_name": settings.model_name, "load_time_s": round(elapsed, 2)},
                )
            return cls._model

    @classmethod
    async def reset_model(cls) -> None:
        async with cls._model_lock:
            cls._model = None

    async def rerank(
            self,
            query: str,
            candidates: list[str],
            top_n: int,
    ) -> list[int]:
        if not candidates:
            return []

        if top_n <= 0:
            raise RerankerExecutionException(f"top_n must be a positive integer, got {top_n}.")

        top_n = min(top_n, len(candidates))

        logger.debug(
            "Running cross-encoder reranking.",
            extra={
                "model_name": self._settings.model_name,
                "total_candidates": len(candidates),
                "top_n": top_n,
                "min_score": self._settings.min_score,
            },
        )

        try:
            model = await self._get_or_load_model(self._settings)
            pairs = [(query, candidate) for candidate in candidates]

            loop = asyncio.get_running_loop()
            predict_fn = partial(
                model.predict,
                pairs,
                batch_size=self._settings.batch_size,
                show_progress_bar=False,
            )
            scores = await loop.run_in_executor(None, predict_fn)

            indexed: list[tuple[int, float]] = sorted(
                enumerate(scores),
                key=lambda item: float(item[1]),
                reverse=True,
            )
            top_indexed = indexed[:top_n]

            selected_indices = [
                idx for idx, score in top_indexed
                if float(score) >= self._settings.min_score
            ]

            if not selected_indices:
                logger.warning(
                    "No candidates above min_score threshold; using top-k without score filter.",
                    extra={"top_n": top_n, "min_score": self._settings.min_score},
                )
                selected_indices = [idx for idx, _ in top_indexed]

            logger.debug(
                "Cross-encoder reranking complete.",
                extra={
                    "kept": len(selected_indices),
                    "scores": [round(float(s), 3) for _, s in top_indexed],
                },
            )
            return selected_indices

        except RerankerExecutionException:
            raise
        except (MemoryError, SystemExit, KeyboardInterrupt):
            raise
        except Exception:
            logger.warning(
                "Cross-encoder reranking failed; falling back to original top-k order.",
                exc_info=True,
            )
            return list(range(top_n))
