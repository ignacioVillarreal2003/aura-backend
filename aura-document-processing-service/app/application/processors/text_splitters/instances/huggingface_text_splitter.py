import logging
from typing import Optional
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings

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
            embeddings = HuggingFaceEmbeddings(
                model_name=self._settings.huggingface_model,
                model_kwargs={
                    "device": self._settings.huggingface_device
                }
            )

            splitter_kwargs: dict = {
                "breakpoint_threshold_type": self._settings.huggingface_breakpoint_threshold_type
            }

            if self._settings.huggingface_breakpoint_threshold_amount is not None:
                splitter_kwargs["breakpoint_threshold_amount"] = self._settings.huggingface_breakpoint_threshold_amount

            self._splitter = SemanticChunker(embeddings, **splitter_kwargs)

            logger.info(
                "The Hugging Face semantic text splitter was initialized successfully.",
                extra={
                    "model": self._settings.huggingface_model,
                    "device": self._settings.huggingface_device,
                    "breakpoint_type": self._settings.huggingface_breakpoint_threshold_type,
                    "breakpoint_amount": self._settings.huggingface_breakpoint_threshold_amount
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
