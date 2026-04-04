import logging
from typing import Optional
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings

from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    TextSplitterInitializationException,
    TextSplitterExecutionException
)
from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface
from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings

logger = logging.getLogger(__name__)


class HuggingFaceTextSplitter(TextSplitterInterface):
    def __init__(self, text_splitter_settings: TextSplitterSettings) -> None:
        self._settings = text_splitter_settings
        self._splitter: Optional[SemanticChunker] = None

        try:
            embeddings = HuggingFaceEmbeddings(
                model_name=self._settings.huggingface_model,
                model_kwargs={"device": self._settings.huggingface_device}
            )

            splitter_kwargs: dict = {
                "breakpoint_threshold_type": self._settings.huggingface_breakpoint_threshold_type,
            }

            if self._settings.huggingface_breakpoint_threshold_amount is not None:
                splitter_kwargs["breakpoint_threshold_amount"] = (
                    self._settings.huggingface_breakpoint_threshold_amount
                )

            self._splitter = SemanticChunker(embeddings, **splitter_kwargs)

            logger.info(
                "HuggingFaceTextSplitter initialized successfully",
                extra={
                    "model": self._settings.huggingface_model,
                    "device": self._settings.huggingface_device,
                    "breakpoint_type": self._settings.huggingface_breakpoint_threshold_type,
                    "breakpoint_amount": self._settings.huggingface_breakpoint_threshold_amount
                }
            )

        except Exception as e:
            logger.exception("Failed to initialize HuggingFaceTextSplitter")
            raise TextSplitterInitializationException(
                f"HuggingFaceTextSplitter initialization failed: {e}"
            ) from e

    def split_text(self, text: str) -> list[str]:
        if not text or not text.strip():
            logger.debug("split_text received empty text, returning empty list")
            return []

        text_length = len(text)

        if text_length > self._settings.max_text_length:
            raise TextSplitterExecutionException(
                f"Text length ({text_length}) exceeds maximum allowed "
                f"({self._settings.max_text_length})"
            )

        logger.debug(
            "Splitting text semantically",
            extra={
                "text_length": text_length,
                "breakpoint_type": self._settings.huggingface_breakpoint_threshold_type
            }
        )

        try:
            splits = self._splitter.split_text(text)

            logger.info(
                "Text split completed",
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
                "Failed to split text semantically",
                extra={"model": self._settings.huggingface_model}
            )
            raise TextSplitterExecutionException(
                f"HuggingFaceTextSplitter failed to split text: {e}"
            ) from e
