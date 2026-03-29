import asyncio
import logging
from datetime import timedelta
from typing import Optional
from aiobreaker import CircuitBreaker as AioBreaker
from langchain_ollama import OllamaEmbeddings
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential
)

from app.application.processors.embedders.embedder_settings import EmbedderSettings
from app.application.processors.embedders.exceptions.embedder_exception import (
    EmbedderInitializationException,
    EmbedDocumentsException,
    EmbedQueryException
)
from app.application.processors.embedders.interfaces.embedder_interface import EmbedderInterface

logger = logging.getLogger(__name__)


class OllamaEmbedder(EmbedderInterface):
    def __init__(self, embedder_settings: EmbedderSettings) -> None:
        self._settings = embedder_settings

        self._retry_decorator = retry(
            stop=stop_after_attempt(self._settings.ollama_max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=self._settings.ollama_retry_delay,
                max=self._settings.ollama_retry_max_delay,
            ),
            retry=retry_if_exception_type(Exception),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

        self._circuit_breaker = AioBreaker(
            fail_max=self._settings.ollama_circuit_breaker_threshold,
            timeout_duration=timedelta(seconds=self._settings.ollama_circuit_breaker_timeout),
        )

        self._model: Optional[OllamaEmbeddings] = None

        try:
            self._model = OllamaEmbeddings(
                model=self._settings.ollama_model,
                base_url=self._settings.ollama_base_url,
            )
            logger.info(
                "OllamaEmbedder initialized successfully",
                extra={
                    "model": self._settings.ollama_model,
                    "base_url": self._settings.ollama_base_url,
                    "max_batch_size": self._settings.ollama_max_batch_size,
                    "timeout": self._settings.ollama_request_timeout,
                    "max_retries": self._settings.ollama_max_retries,
                    "circuit_breaker_threshold": self._settings.ollama_circuit_breaker_threshold,
                },
            )
        except Exception as e:
            logger.exception("Failed to initialize OllamaEmbedder")
            raise EmbedderInitializationException(
                f"OllamaEmbedder initialization failed: {e}"
            ) from e

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            raise ValueError("texts cannot be empty")

        self._validate_texts(texts)

        if len(texts) > self._settings.ollama_max_batch_size:
            logger.info(
                "Splitting large batch into smaller batches",
                extra={
                    "total_texts": len(texts),
                    "batch_size": self._settings.ollama_max_batch_size
                }
            )
            return self._embed_in_batches(texts)

        return self._embed_single_batch(texts)

    def embed_query(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValueError("text cannot be empty or blank")

        if len(text) > self._settings.ollama_max_text_length:
            raise EmbedQueryException(
                f"Query text exceeds max length "
                f"({len(text)} > {self._settings.ollama_max_text_length})"
            )

        logger.debug("Generating query embedding", extra={"length": len(text)})

        try:
            embedding = self._retry_decorator(self._model.embed_query)(text)
            logger.info("Query embedding generated successfully")
            return embedding
        except Exception as e:
            raise EmbedQueryException(
                f"OllamaEmbedder failed to generate query embedding: {e}"
            ) from e

    async def aembed_query(self, text: str) -> list[float]:
        return await self._circuit_breaker.call(asyncio.to_thread, self.embed_query, text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._circuit_breaker.call(asyncio.to_thread, self.embed_documents, texts)

    def _embed_single_batch(self, texts: list[str]) -> list[list[float]]:
        logger.debug(
            "Generating document_controllers embeddings",
            extra={
                "count": len(texts),
                "avg_length": sum(len(t) for t in texts) // len(texts) if texts else 0
            },
        )
        try:
            embeddings = self._retry_decorator(self._model.embed_documents)(texts)
            logger.info(
                "Document embeddings generated successfully",
                extra={"count": len(embeddings)}
            )
            return embeddings
        except Exception as e:
            raise EmbedDocumentsException(
                f"OllamaEmbedder failed to generate document_controllers embeddings: {e}"
            ) from e

    def _embed_in_batches(self, texts: list[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        batch_size = self._settings.ollama_max_batch_size
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
            if len(text) > self._settings.ollama_max_text_length:
                raise ValueError(
                    f"texts[{i}] exceeds max length "
                    f"({len(text)} > {self._settings.ollama_max_text_length})"
                )
