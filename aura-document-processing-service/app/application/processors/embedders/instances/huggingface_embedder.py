import asyncio
import logging
from datetime import timedelta
from typing import Callable, Optional
from aiobreaker import CircuitBreaker as AioBreaker
from aiobreaker import CircuitBreakerError
from tenacity import before_sleep_log, retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.application.processors._hf_model_cache import (
    get_or_create as _get_or_create_hf_embeddings,
    get_sentence_transformer as _get_sentence_transformer,
)
from app.application.processors.embedders.embedder_settings import EmbedderSettings
from app.application.processors.embedders.exceptions.embedder_exception import (
    EmbedderInitializationException,
    EmbedDocumentsException,
    EmbedQueryException,
)
from app.application.processors.embedders.instances.base_embedder import BaseEmbedder

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN_HINT = 2.0


def _is_cuda_oom(exc: BaseException) -> bool:
    if type(exc).__name__ == "OutOfMemoryError":
        return True
    message = str(exc).lower()
    return "out of memory" in message or "cuda oom" in message


def _is_retryable_runtime_error(exc: BaseException) -> bool:
    if isinstance(exc, (RuntimeError, OSError)):
        return not _is_cuda_oom(exc)
    return False


class HuggingFaceEmbedder(BaseEmbedder):
    def __init__(
            self,
            embedder_settings: EmbedderSettings
    ) -> None:
        self._settings = embedder_settings

        self._max_text_length = self._settings.max_text_length
        self._max_batch_size = self._settings.max_batch_size
        self._max_batch_tokens = self._settings.max_batch_tokens

        _retry = retry(
            stop=stop_after_attempt(self._settings.max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=self._settings.retry_delay,
                max=self._settings.retry_max_delay,
            ),
            retry=retry_if_exception(_is_retryable_runtime_error),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )

        self._circuit_breaker = AioBreaker(
            fail_max=self._settings.circuit_breaker_threshold,
            timeout_duration=timedelta(seconds=self._settings.circuit_breaker_timeout)
        )

        self._model = None

        try:
            self._model, self._encode_lock = _get_or_create_hf_embeddings(
                model_name=self._settings.huggingface_model,
                device=self._settings.huggingface_device,
                normalize_embeddings=self._settings.huggingface_normalize_embeddings,
                token=self._settings.huggingface_token,
                max_seq_length=self._settings.huggingface_max_seq_length,
                torch_dtype=self._settings.huggingface_torch_dtype,
            )

            st_model = _get_sentence_transformer(self._model)
            self._max_seq_length: Optional[int] = getattr(st_model, "max_seq_length", None)
            self._tokenizer = getattr(st_model, "tokenizer", None)

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
                    "torch_dtype": self._settings.huggingface_torch_dtype,
                    "normalize": self._settings.huggingface_normalize_embeddings,
                    "dimensions": self._settings.vector_dimension,
                    "max_seq_length": self._max_seq_length,
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
        texts = self._sanitize_documents(texts)
        if self._settings.huggingface_embed_instruction:
            texts = [self._settings.huggingface_embed_instruction + t for t in texts]

        token_lengths = self._token_lengths(texts)
        self._warn_if_truncated(texts, token_lengths)

        batches = self._build_batches(texts, token_lengths)
        if len(batches) <= 1:
            return self._embed_single_batch(texts)

        logger.info(
            "Splitting into token-aware embedding batches.",
            extra={
                "total_texts": len(texts),
                "batches": len(batches),
                "max_batch_size": self._max_batch_size,
                "max_batch_tokens": self._max_batch_tokens,
            }
        )
        all_embeddings: list[list[float]] = []
        for batch in batches:
            all_embeddings.extend(self._embed_single_batch(batch))
        return all_embeddings

    def embed_query(
            self,
            text: str
    ) -> list[float]:
        if self._settings.huggingface_query_instruction:
            text = self._settings.huggingface_query_instruction + text

        self._validate_text(text)
        self._warn_if_truncated([text])

        logger.debug(
            "Generating a query embedding.",
            extra={
                "length": len(text)
            }
        )

        try:
            with self._encode_lock:
                embedding = self._embed_query_with_retry(text)
        except Exception as e:
            raise EmbedQueryException("Failed to generate the query embedding with Hugging Face.") from e

        if not self._is_finite_vector(embedding):
            raise EmbedQueryException(
                "The embedding model produced a non-finite (NaN/Inf) query vector; "
                "consider EMBEDDER_HUGGINGFACE_TORCH_DTYPE=bfloat16 or float32."
            )

        logger.info("The query embedding was generated successfully.")
        return embedding

    async def aembed_query(
            self,
            text: str
    ) -> list[float]:
        try:
            return await self._circuit_breaker.call(asyncio.to_thread, self.embed_query, text)
        except CircuitBreakerError as e:
            raise EmbedQueryException(
                "The Hugging Face embedder is temporarily unavailable (circuit breaker is open)."
            ) from e

    async def aembed_documents(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        try:
            return await self._circuit_breaker.call(asyncio.to_thread, self.embed_documents, texts)
        except CircuitBreakerError as e:
            raise EmbedDocumentsException(
                "The Hugging Face embedder is temporarily unavailable (circuit breaker is open)."
            ) from e

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
            with self._encode_lock:
                embeddings = self._embed_documents_with_retry(texts)
        except Exception as e:
            raise EmbedDocumentsException("Failed to generate document embeddings with Hugging Face.") from e

        self._assert_finite_embeddings(embeddings)
        logger.info(
            "The document embeddings were generated successfully.",
            extra={
                "count": len(embeddings)
            }
        )
        return embeddings

    def _token_lengths(
            self,
            texts: list[str]
    ) -> Optional[list[int]]:
        if self._tokenizer is None:
            return None

        lengths: list[int] = []
        for text in texts:
            try:
                lengths.append(len(self._tokenizer.encode(text, add_special_tokens=True)))
            except Exception:
                lengths.append(int(len(text) / _CHARS_PER_TOKEN_HINT) + 1)
        return lengths

    def _build_batches(
            self,
            texts: list[str],
            token_lengths: Optional[list[int]]
    ) -> list[list[str]]:
        max_count = self._max_batch_size
        budget = self._max_batch_tokens

        if not token_lengths or budget <= 0:
            return [texts[i: i + max_count] for i in range(0, len(texts), max_count)]

        batches: list[list[str]] = []
        current: list[str] = []
        current_max_tokens = 0
        for text, tokens in zip(texts, token_lengths):
            prospective_max = max(current_max_tokens, tokens)
            if current and (
                    len(current) + 1 > max_count
                    or prospective_max * (len(current) + 1) > budget
            ):
                batches.append(current)
                current = []
                current_max_tokens = 0
            current.append(text)
            current_max_tokens = max(current_max_tokens, tokens)
        if current:
            batches.append(current)
        return batches

    def _warn_if_truncated(
            self,
            texts: list[str],
            token_lengths: Optional[list[int]] = None
    ) -> None:
        if self._max_seq_length is None:
            return
        if token_lengths is None:
            token_lengths = self._token_lengths(texts)
        if token_lengths is None:
            return

        truncated = 0
        max_observed_tokens = 0
        for token_count in token_lengths:
            if token_count > self._max_seq_length:
                truncated += 1
                max_observed_tokens = max(max_observed_tokens, token_count)

        if truncated:
            logger.warning(
                "Some inputs exceed the model token window and will be truncated by the tokenizer; "
                "consider smaller chunks to avoid losing content.",
                extra={
                    "model": self._settings.huggingface_model,
                    "max_seq_length": self._max_seq_length,
                    "truncated_inputs": truncated,
                    "total_inputs": len(texts),
                    "max_observed_tokens": max_observed_tokens,
                }
            )
