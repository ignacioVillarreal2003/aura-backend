import asyncio
import logging
from datetime import timedelta
from typing import Callable, Optional
from aiobreaker import CircuitBreaker as AioBreaker
from langchain_huggingface import HuggingFaceEmbeddings
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.application.processors.embedders.embedder_settings import EmbedderSettings
from app.application.processors.embedders.exceptions.embedder_exception import (
    EmbedderInitializationException,
    EmbedDocumentsException,
    EmbedQueryException,
)
from app.application.processors.embedders.instances.base_embedder import BaseEmbedder

logger = logging.getLogger(__name__)

_RETRYABLE_EXCEPTIONS = (RuntimeError, OSError)


class HuggingFaceEmbedder(BaseEmbedder):
    def __init__(self, embedder_settings: EmbedderSettings) -> None:
        self._settings = embedder_settings

        self._max_text_length = self._settings.max_text_length
        self._max_batch_size = self._settings.max_batch_size

        _retry = retry(
            stop=stop_after_attempt(self._settings.max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=self._settings.retry_delay,
                max=self._settings.retry_max_delay,
            ),
            retry=retry_if_exception_type(_RETRYABLE_EXCEPTIONS),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

        self._circuit_breaker = AioBreaker(
            fail_max=self._settings.circuit_breaker_threshold,
            timeout_duration=timedelta(seconds=self._settings.circuit_breaker_timeout),
        )

        self._model: Optional[HuggingFaceEmbeddings] = None

        try:
            self._model = HuggingFaceEmbeddings(
                model_name=self._settings.huggingface_model,
                model_kwargs={"device": self._settings.huggingface_device},
                encode_kwargs={
                    "normalize_embeddings": self._settings.huggingface_normalize_embeddings
                },
            )

            self._embed_query_with_retry: Callable[[str], list[float]] = _retry(
                self._model.embed_query
            )
            self._embed_documents_with_retry: Callable[[list[str]], list[list[float]]] = _retry(
                self._model.embed_documents
            )

            probe = self._embed_query_with_retry("probe")
            dimensions = len(probe)

            logger.info(
                "HuggingFaceEmbedder initialized successfully",
                extra={
                    "model": self._settings.huggingface_model,
                    "device": self._settings.huggingface_device,
                    "normalize": self._settings.huggingface_normalize_embeddings,
                    "dimensions": dimensions,
                    "max_batch_size": self._settings.max_batch_size,
                    "max_retries": self._settings.max_retries,
                    "circuit_breaker_threshold": self._settings.circuit_breaker_threshold,
                },
            )

        except EmbedderInitializationException:
            raise
        except Exception as e:
            logger.exception("Failed to initialize HuggingFaceEmbedder")
            raise EmbedderInitializationException(
                f"HuggingFaceEmbedder initialization failed: {e}"
            ) from e

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._validate_texts(texts)

        if len(texts) > self._max_batch_size:
            return self._embed_in_batches(texts)

        return self._embed_single_batch(texts)

    def embed_query(self, text: str) -> list[float]:
        self._validate_text(text)

        logger.debug("Generating query embedding", extra={"length": len(text)})

        try:
            embedding = self._embed_query_with_retry(text)
            logger.info("Query embedding generated successfully")
            return embedding
        except Exception as e:
            raise EmbedQueryException(
                f"HuggingFaceEmbedder failed to generate query embedding: {e}"
            ) from e

    async def aembed_query(self, text: str) -> list[float]:
        return await self._circuit_breaker.call(asyncio.to_thread, self.embed_query, text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._circuit_breaker.call(asyncio.to_thread, self.embed_documents, texts)

    def _embed_single_batch(self, texts: list[str]) -> list[list[float]]:
        logger.debug(
            "Generating document embeddings",
            extra={
                "count": len(texts),
                "avg_length": sum(len(t) for t in texts) // len(texts) if texts else 0,
            },
        )
        try:
            embeddings = self._embed_documents_with_retry(texts)
            logger.info(
                "Document embeddings generated successfully",
                extra={"count": len(embeddings)},
            )
            return embeddings
        except Exception as e:
            raise EmbedDocumentsException(
                f"HuggingFaceEmbedder failed to generate document embeddings: {e}"
            ) from e
