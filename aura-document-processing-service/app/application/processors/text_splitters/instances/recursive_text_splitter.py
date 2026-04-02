import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    TextSplitterInitializationException,
    TextSplitterExecutionException,
)
from app.application.processors.text_splitters.instances.base_text_splitter import BaseTextSplitter
from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings

logger = logging.getLogger(__name__)


class RecursiveTextSplitter(BaseTextSplitter):
    def __init__(self, text_splitter_settings: TextSplitterSettings) -> None:
        self._settings = text_splitter_settings
        self._max_text_length = self._settings.max_text_length

        try:
            self._splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                encoding_name=self._settings.recursive_encoding_name,
                chunk_size=self._settings.recursive_split_size,
                chunk_overlap=self._settings.recursive_split_overlap,
            )
            logger.info(
                "RecursiveTextSplitter initialized successfully",
                extra={
                    "encoding": self._settings.recursive_encoding_name,
                    "split_size": self._settings.recursive_split_size,
                    "split_overlap": self._settings.recursive_split_overlap,
                },
            )
        except Exception as e:
            logger.exception("Failed to initialize RecursiveTextSplitter")
            raise TextSplitterInitializationException(
                f"RecursiveTextSplitter initialization failed: {e}"
            ) from e

    def split_text(self, text: str) -> list[str]:
        if not text or not text.strip():
            logger.debug("split_text received empty text, returning empty list")
            return []

        self._validate_text(text)

        logger.debug(
            "Splitting text",
            extra={
                "text_length": len(text),
                "split_size": self._settings.recursive_split_size,
                "split_overlap": self._settings.recursive_split_overlap,
            },
        )

        try:
            splits = self._splitter.split_text(text)

            logger.info(
                "Text split completed",
                extra={
                    "splits_created": len(splits),
                    "avg_split_length": sum(len(c) for c in splits) // len(splits) if splits else 0,
                },
            )

            return splits

        except TextSplitterExecutionException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to split text",
                extra={
                    "split_size": self._settings.recursive_split_size,
                    "split_overlap": self._settings.recursive_split_overlap,
                },
            )
            raise TextSplitterExecutionException(
                f"RecursiveTextSplitter failed to split text: {e}"
            ) from e
