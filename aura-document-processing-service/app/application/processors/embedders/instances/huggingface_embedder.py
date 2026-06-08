import asyncio
import logging
from datetime import timedelta
from typing import Callable
from aiobreaker import CircuitBreaker as AioBreaker
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.application.processors._hf_model_cache import get_or_create as _get_or_create_hf_embeddings
from app.application.processors.embedders.embedder_settings import EmbedderSettings
from app.application.processors.embedders.exceptions.embedder_exception import (
    EmbedderInitializationException,
    EmbedDocumentsException,
    EmbedQueryException
)
from app.application.processors.embedders.instances.base_embedder import BaseEmbedder

logger = logging.getLogger(__name__)


class HuggingFaceEmbedder(BaseEmbedder):
    def __init__(
            self,
            embedder_settings: EmbedderSettings
    ) -> None:
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
            retry=retry_if_exception_type((RuntimeError, OSError)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )

        self._circuit_breaker = AioBreaker(
            fail_max=self._settings.circuit_breaker_threshold,
            timeout_duration=timedelta(seconds=self._settings.circuit_breaker_timeout)
        )

        self._model = None

        try:
            self._model = _get_or_create_hf_embeddings(
                model_name=self._settings.huggingface_model,
                device=self._settings.huggingface_device,
                normalize_embeddings=self._settings.huggingface_normalize_embeddings,
                token=self._settings.huggingface_token,
            )

            self._embed_query_with_retry: Callable[[str], list[float]] = _retry(
                self._model.embed_query
            )
            self._embed_documents_with_retry: Callable[[list[str]], list[list[float]]] = _retry(
                self._model.embed_documents
            )

            logger.info(
                "The Hugging Face embedder was initialized successfully.",
                extra={
                    "model": self._settings.huggingface_model,
                    "device": self._settings.huggingface_device,
                    "normalize": self._settings.huggingface_normalize_embeddings,
                    "dimensions": self._settings.vector_dimension,
                    "max_batch_size": self._settings.max_batch_size,
                    "max_retries": self._settings.max_retries,
                    "circuit_breaker_threshold": self._settings.circuit_breaker_threshold
                }
            )

        except EmbedderInitializationException:
            raise
        except Exception as e:
            logger.exception("Failed to initialize the Hugging Face embedder.")
            raise EmbedderInitializationException("Failed to initialize the Hugging Face embedder.") from e

    def embed_documents(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        if self._settings.huggingface_embed_instruction:
            texts = [self._settings.huggingface_embed_instruction + t for t in texts]

        self._validate_texts(texts)

        if len(texts) > self._max_batch_size:
            logger.info(
                "Splitting a large batch into smaller embedding batches.",
                extra={
                    "total_texts": len(texts),
                    "batch_size": self._max_batch_size
                }
            )
            return self._embed_in_batches(texts)

        return self._embed_single_batch(texts)

    def embed_query(
            self,
            text: str
    ) -> list[float]:
        if self._settings.huggingface_query_instruction:
            text = self._settings.huggingface_query_instruction + text

        self._validate_text(text)

        logger.debug(
            "Generating a query embedding.",
            extra={
                "length": len(text)
            }
        )

        try:
            embedding = self._embed_query_with_retry(text)
            logger.info("The query embedding was generated successfully.")
            return embedding
        except Exception as e:
            raise EmbedQueryException("Failed to generate the query embedding with Hugging Face.") from e

    async def aembed_query(
            self,
            text: str
    ) -> list[float]:
        return await self._circuit_breaker.call(asyncio.to_thread, self.embed_query, text)

    async def aembed_documents(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        return await self._circuit_breaker.call(asyncio.to_thread, self.embed_documents, texts)

    def _embed_single_batch(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        logger.debug(
            "Generating document embeddings.",
            extra={
                "count": len(texts),
                "avg_length": sum(len(t) for t in texts) // len(texts) if texts else 0
            }
        )
        try:
            embeddings = self._embed_documents_with_retry(texts)
            logger.info(
                "The document embeddings were generated successfully.",
                extra={
                    "count": len(embeddings)
                }
            )
            return embeddings
        except Exception as e:
            raise EmbedDocumentsException("Failed to generate document embeddings with Hugging Face.") from e
