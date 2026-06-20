import logging
from abc import abstractmethod

from app.application.processors.text_splitters.dtos.document_chunk import DocumentChunk
from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    TextSplitterExecutionException
)
from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface

logger = logging.getLogger(__name__)

_DEFAULT_MIN_CHUNK_CHARS = 150


class BaseTextSplitter(TextSplitterInterface):
    _max_text_length: int
    _min_chunk_chars: int = _DEFAULT_MIN_CHUNK_CHARS

    def _validate_text(
            self,
            text: str
    ) -> None:
        if not text or not text.strip():
            raise TextSplitterExecutionException("The text cannot be empty or blank.")

        if len(text) > self._max_text_length:
            raise TextSplitterExecutionException("The text exceeds the maximum allowed length.")

    def _merge_short_chunks(self, chunks: list[str]) -> list[str]:
        if not chunks or self._min_chunk_chars <= 0:
            return chunks

        result: list[str] = []
        for chunk in chunks:
            stripped = chunk.strip()
            if not stripped:
                continue
            if result and len(stripped) < self._min_chunk_chars:
                result[-1] = result[-1] + " " + stripped
                logger.debug(
                    "Merged short chunk into previous.",
                    extra={"short_chunk_length": len(stripped), "min_chunk_chars": self._min_chunk_chars}
                )
            else:
                result.append(stripped)

        if len(result) >= 2 and len(result[0]) < self._min_chunk_chars:
            logger.debug(
                "Merged short leading chunk into next.",
                extra={"short_chunk_length": len(result[0]), "min_chunk_chars": self._min_chunk_chars}
            )
            result[1] = result[0] + " " + result[1]
            result.pop(0)

        return result

    @abstractmethod
    def split_text(
            self,
            text: str
    ) -> list[DocumentChunk]:
        pass
