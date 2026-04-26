import logging
from typing import Optional
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from transformers import AutoTokenizer

from app.application.processors._hf_model_cache import get_or_create as _get_or_create_hf_embeddings

from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    TextSplitterInitializationException,
    TextSplitterExecutionException
)
from app.application.processors.text_splitters.instances.base_text_splitter import BaseTextSplitter
from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings

logger = logging.getLogger(__name__)


class HuggingFaceTextSplitter(BaseTextSplitter):
    def __init__(
            self,
            text_splitter_settings: TextSplitterSettings
    ) -> None:
        self._settings = text_splitter_settings
        self._max_text_length = self._settings.max_text_length
        self._splitter: Optional[SemanticChunker] = None

        try:
            embeddings = _get_or_create_hf_embeddings(
                model_name=self._settings.huggingface_model,
                device=self._settings.huggingface_device,
            )

            splitter_kwargs: dict = {
                "breakpoint_threshold_type": self._settings.huggingface_breakpoint_threshold_type
            }

            if self._settings.huggingface_breakpoint_threshold_amount is not None:
                splitter_kwargs["breakpoint_threshold_amount"] = self._settings.huggingface_breakpoint_threshold_amount

            self._splitter = SemanticChunker(embeddings, **splitter_kwargs)

            tokenizer = AutoTokenizer.from_pretrained(self._settings.huggingface_model)
            self._size_splitter = RecursiveCharacterTextSplitter.from_huggingface_tokenizer(
                tokenizer,
                chunk_size=self._settings.huggingface_max_chunk_tokens,
                chunk_overlap=self._settings.huggingface_chunk_token_overlap,
            )
            self._tokenizer = tokenizer

            logger.info(
                "The Hugging Face semantic text splitter was initialized successfully.",
                extra={
                    "model": self._settings.huggingface_model,
                    "device": self._settings.huggingface_device,
                    "breakpoint_type": self._settings.huggingface_breakpoint_threshold_type,
                    "breakpoint_amount": self._settings.huggingface_breakpoint_threshold_amount,
                    "max_chunk_tokens": self._settings.huggingface_max_chunk_tokens,
                    "chunk_token_overlap": self._settings.huggingface_chunk_token_overlap,
                }
            )

        except Exception as e:
            logger.exception("Failed to initialize the Hugging Face semantic text splitter.")
            raise TextSplitterInitializationException(
                "Failed to initialize the Hugging Face semantic text splitter."
            ) from e

    def split_text(self, text: str) -> list[str]:
        if not text or not text.strip():
            logger.debug("split_text received empty text; returning an empty list.")
            return []

        self._validate_text(text)

        logger.debug(
            "Splitting text with semantic chunking.",
            extra={
                "text_length": len(text),
                "breakpoint_type": self._settings.huggingface_breakpoint_threshold_type
            }
        )

        try:
            splits = self._splitter.split_text(text)
            splits = self._enforce_token_limit(splits)

            logger.info(
                "The text was split successfully with semantic chunking.",
                extra={
                    "splits_created": len(splits),
                    "avg_split_length": sum(len(c) for c in splits) // len(splits) if splits else 0
                }
            )

            return splits

        except TextSplitterExecutionException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to split text with semantic chunking.",
                extra={
                    "model": self._settings.huggingface_model
                }
            )
            raise TextSplitterExecutionException("Failed to split the text with semantic chunking.") from e

    def _enforce_token_limit(self, chunks: list[str]) -> list[str]:
        result: list[str] = []
        oversized = 0
        for chunk in chunks:
            token_count = len(self._tokenizer.encode(chunk, add_special_tokens=True))
            if token_count <= self._settings.huggingface_max_chunk_tokens:
                result.append(chunk)
            else:
                sub_chunks = self._size_splitter.split_text(chunk)
                result.extend(sub_chunks)
                oversized += 1
        if oversized:
            logger.debug(
                "Some semantic chunks exceeded the token limit and were sub-split.",
                extra={"oversized_chunks": oversized, "total_after": len(result)},
            )
        return result
