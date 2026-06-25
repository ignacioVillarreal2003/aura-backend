import logging
import math
from abc import abstractmethod

from app.application.processors.embedders.exceptions.embedder_exception import (
    EmbedDocumentsException,
    EmbedQueryException
)
from app.application.processors.embedders.interfaces.embedder_interface import EmbedderInterface

logger = logging.getLogger(__name__)


_BLANK_PLACEHOLDER = " "


class BaseEmbedder(EmbedderInterface):
    _max_text_length: int
    _max_batch_size: int

    def _validate_text(
            self,
            text: str
    ) -> None:
        if not text or not text.strip():
            raise EmbedQueryException("The query text cannot be empty or blank.")

        if len(text) > self._max_text_length:
            raise EmbedQueryException("The query text exceeds the maximum allowed length.")

    def _sanitize_documents(
            self,
            texts: list[str]
    ) -> list[str]:
        if not texts:
            raise EmbedDocumentsException("The document texts list cannot be empty.")

        sanitized: list[str] = []
        blank_count = 0
        truncated_count = 0
        for text in texts:
            if not text or not text.strip():
                sanitized.append(_BLANK_PLACEHOLDER)
                blank_count += 1
                continue
            if len(text) > self._max_text_length:
                text = text[: self._max_text_length]
                truncated_count += 1
            sanitized.append(text)

        if blank_count:
            logger.warning(
                "Replaced blank document texts with a placeholder to keep batch alignment.",
                extra={"blank_count": blank_count, "total": len(texts)},
            )
        if truncated_count:
            logger.warning(
                "Truncated over-length document texts to the maximum allowed length.",
                extra={"truncated_count": truncated_count, "max_text_length": self._max_text_length},
            )
        return sanitized

    @staticmethod
    def _is_finite_vector(
            vector: list[float]
    ) -> bool:
        if not vector:
            return True
        first = vector[0]
        last = vector[-1]
        return not (first != first or last != last
                    or math.isinf(first) or math.isinf(last))

    @staticmethod
    def _assert_finite_embeddings(
            embeddings: list[list[float]]
    ) -> None:
        for vector in embeddings:
            if not BaseEmbedder._is_finite_vector(vector):
                raise EmbedDocumentsException(
                    "The embedding model produced a non-finite (NaN/Inf) vector; "
                    "consider EMBEDDER_HUGGINGFACE_TORCH_DTYPE=bfloat16 or float32."
                )

    def _embed_in_batches(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        batch_size = self._max_batch_size
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            batch_num = (i // batch_size) + 1
            logger.debug(
                "Processing an embedding batch.",
                extra={
                    "batch": f"{batch_num}/{total_batches}",
                    "batch_size": len(batch)
                }
            )
            all_embeddings.extend(self._embed_single_batch(batch))

        logger.info(
            "All embedding batches were processed successfully.",
            extra={
                "total_texts": len(texts),
                "total_batches": total_batches
            }
        )
        return all_embeddings

    @abstractmethod
    def _embed_single_batch(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        pass
