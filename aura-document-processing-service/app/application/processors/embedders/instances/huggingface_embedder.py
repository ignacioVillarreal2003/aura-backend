import asyncio
import logging
from typing import Optional
from langchain_huggingface import HuggingFaceEmbeddings

from app.application.processors.embedders.embedder_settings import EmbedderSettings
from app.application.processors.embedders.exceptions.embedder_exception import (
    EmbedderInitializationException,
    EmbedDocumentsException,
    EmbedQueryException,
)
from app.application.processors.embedders.interfaces.embedder_interface import EmbedderInterface

logger = logging.getLogger(__name__)


class HuggingFaceEmbedder(EmbedderInterface):
    def __init__(self, embedder_settings: EmbedderSettings) -> None:
        self._settings = embedder_settings
        self._model: Optional[HuggingFaceEmbeddings] = None

        try:
            self._model = HuggingFaceEmbeddings(
                model_name=self._settings.huggingface_model,
                model_kwargs={"device": self._settings.huggingface_device},
                encode_kwargs={"normalize_embeddings": self._settings.huggingface_normalize_embeddings}
            )

            probe = self._model.embed_query("probe")
            dimensions = len(probe)

            logger.info(
                "HuggingFaceEmbedder initialized successfully",
                extra={
                    "model": self._settings.huggingface_model,
                    "device": self._settings.huggingface_device,
                    "normalize": self._settings.huggingface_normalize_embeddings,
                    "dimensions": dimensions,
                    "max_batch_size": self._settings.huggingface_max_batch_size
                }
            )

        except Exception as e:
            logger.exception("Failed to initialize HuggingFaceEmbedder")
            raise EmbedderInitializationException(
                f"HuggingFaceEmbedder initialization failed: {e}"
            ) from e

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            raise ValueError("texts cannot be empty")

        self._validate_texts(texts)

        if len(texts) > self._settings.huggingface_max_batch_size:
            return self._embed_in_batches(texts)

        return self._embed_single_batch(texts)

    def embed_query(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("text cannot be empty or blank")

        if len(text) > self._settings.huggingface_max_text_length:
            raise EmbedQueryException(
                f"Query text exceeds max length "
                f"({len(text)} > {self._settings.huggingface_max_text_length})"
            )

        logger.debug("Generating query embedding", extra={"length": len(text)})

        try:
            embedding = self._model.embed_query(text)
            logger.info("Query embedding generated successfully")
            return embedding
        except Exception as e:
            raise EmbedQueryException(
                f"HuggingFaceEmbedder failed to generate query embedding: {e}"
            ) from e

    async def aembed_query(self, text: str) -> list[float]:
        return await asyncio.to_thread(self.embed_query, text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(self.embed_documents, texts)

    def _embed_single_batch(self, texts: list[str]) -> list[list[float]]:
        logger.debug(
            "Generating document_controllers embeddings",
            extra={
                "count": len(texts),
                "avg_length": sum(len(t) for t in texts) // len(texts) if texts else 0
            }
        )
        try:
            embeddings = self._model.embed_documents(texts)
            logger.info(
                "Document embeddings generated successfully",
                extra={"count": len(embeddings)}
            )
            return embeddings
        except Exception as e:
            raise EmbedDocumentsException(
                f"HuggingFaceEmbedder failed to generate document_controllers embeddings: {e}"
            ) from e

    def _embed_in_batches(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        batch_size = self._settings.huggingface_max_batch_size
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            batch_num = (i // batch_size) + 1
            logger.debug(
                "Processing batch",
                extra={"batch": f"{batch_num}/{total_batches}", "batch_size": len(batch)}
            )
            all_embeddings.extend(self._embed_single_batch(batch))

        logger.info(
            "All batches processed successfully",
            extra={"total_texts": len(texts), "total_batches": total_batches}
        )
        return all_embeddings

    def _validate_texts(self, texts: list[str]) -> None:
        for i, text in enumerate(texts):
            if not text or not text.strip():
                raise ValueError(f"texts[{i}] cannot be empty or blank")
            if len(text) > self._settings.huggingface_max_text_length:
                raise ValueError(
                    f"texts[{i}] exceeds max length "
                    f"({len(text)} > {self._settings.huggingface_max_text_length})"
                )
