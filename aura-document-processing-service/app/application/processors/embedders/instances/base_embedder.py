import logging
from abc import abstractmethod

from app.application.processors.embedders.exceptions.embedder_exception import (
    EmbedDocumentsException,
    EmbedQueryException
)
from app.application.processors.embedders.interfaces.embedder_interface import EmbedderInterface

logger = logging.getLogger(__name__)


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

    def _validate_texts(
            self,
            texts: list[str]
    ) -> None:
        if not texts:
            raise EmbedDocumentsException("The document texts list cannot be empty.")

        for text in texts:
            if not text or not text.strip():
                raise EmbedDocumentsException("A document text cannot be empty or blank.")
            if len(text) > self._max_text_length:
                raise EmbedDocumentsException("A document text exceeds the maximum allowed length.")

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
