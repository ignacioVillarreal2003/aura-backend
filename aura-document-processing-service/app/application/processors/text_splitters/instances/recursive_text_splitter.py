import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.application.processors.text_splitters.dtos.document_chunk import DocumentChunk
from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    TextSplitterInitializationException,
    TextSplitterExecutionException,
)
from app.application.processors.text_splitters.instances.base_text_splitter import BaseTextSplitter
from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings

logger = logging.getLogger(__name__)


class RecursiveTextSplitter(BaseTextSplitter):
    def __init__(
            self,
            text_splitter_settings: TextSplitterSettings
    ) -> None:
        self._settings = text_splitter_settings
        self._max_text_length = self._settings.max_text_length

        try:
            self._min_chunk_chars = self._settings.min_chunk_chars
            self._splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                encoding_name=self._settings.recursive_encoding_name,
                chunk_size=self._settings.recursive_split_size,
                chunk_overlap=self._settings.recursive_split_overlap
            )
            logger.info(
                "The recursive text splitter was initialized successfully.",
                extra={
                    "encoding": self._settings.recursive_encoding_name,
                    "split_size": self._settings.recursive_split_size,
                    "split_overlap": self._settings.recursive_split_overlap,
                    "min_chunk_chars": self._settings.min_chunk_chars
                }
            )
        except Exception as e:
            logger.exception("Failed to initialize the recursive text splitter.")
            raise TextSplitterInitializationException("Failed to initialize the recursive text splitter.") from e

    def get_chunk_params(self) -> tuple[int | None, int | None]:
        return self._settings.recursive_split_size, self._settings.recursive_split_overlap

    def split_text(
            self,
            text: str
    ) -> list[DocumentChunk]:
        if not text or not text.strip():
            logger.debug("split_text received empty text; returning an empty list.")
            return []

        self._validate_text(text)

        logger.debug(
            "Splitting text recursively.",
            extra={
                "text_length": len(text),
                "split_size": self._settings.recursive_split_size,
                "split_overlap": self._settings.recursive_split_overlap
            }
        )

        try:
            splits = self._splitter.split_text(text)
            splits = self._merge_short_chunks(splits)

            logger.info(
                "The text was split successfully.",
                extra={
                    "splits_created": len(splits),
                    "avg_split_length": sum(len(c) for c in splits) // len(splits) if splits else 0
                }
            )

            return [DocumentChunk(text=chunk) for chunk in splits]

        except TextSplitterExecutionException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to split the text.",
                extra={
                    "split_size": self._settings.recursive_split_size,
                    "split_overlap": self._settings.recursive_split_overlap
                }
            )
            raise TextSplitterExecutionException("Failed to split the text.") from e
