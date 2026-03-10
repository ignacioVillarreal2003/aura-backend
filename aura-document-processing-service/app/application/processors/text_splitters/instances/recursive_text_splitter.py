import logging
from typing import Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.application.processors.text_splitters.exceptions.text_splitter_exception import TextSplitterExecutionException
from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface
from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings

logger = logging.getLogger(__name__)


class RecursiveTextSplitter(TextSplitterInterface):
    def __init__(
            self,
            text_splitter_settings: Optional[TextSplitterSettings] = None
    ) -> None:
        self._text_splitter_settings = text_splitter_settings

    def split_text(
            self,
            text: str
    ) -> list[str]:
        if not text or not text.strip():
            logger.debug("split_text received empty text, returning empty list")
            return []

        text_length = len(text)

        if text_length > self._text_splitter_settings.max_text_length:
            raise TextSplitterExecutionException(
                f"Text length ({text_length}) exceeds maximum allowed "
                f"({self._text_splitter_settings.max_text_length})"
            )

        logger.debug(
            "Splitting text",
            extra={
                "text_length": text_length,
                "split_size": self._text_splitter_settings.split_size,
                "split_overlap": self._text_splitter_settings.split_overlap
            }
        )

        try:
            splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
                encoding_name=self._text_splitter_settings.recursive_encoding_name,
                chunk_size=self._text_splitter_settings.split_size,
                chunk_overlap=self._text_splitter_settings.split_overlap
            )
            splits = splitter.split_text(text)

            logger.info(
                "Text split completed",
                extra={
                    "splits_created": len(splits),
                    "split_size": self._text_splitter_settings.split_size,
                    "split_overlap": self._text_splitter_settings.split_overlap,
                    "avg_split_length": sum(len(c) for c in splits) // len(splits) if splits else 0
                }
            )

            return splits

        except ValueError:
            raise
        except Exception as e:
            logger.exception(
                "Failed to split text",
                extra={
                    "split_size": self._text_splitter_settings.split_size,
                    "split_overlap": self._text_splitter_settings.split_overlap
                }
            )
            raise TextSplitterExecutionException(f"RecursiveTextSplitterAdapter failed to split text: {str(e)}") from e
