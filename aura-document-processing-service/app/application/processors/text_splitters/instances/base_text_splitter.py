import logging
from abc import abstractmethod

from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    TextSplitterExecutionException
)
from app.application.processors.text_splitters.interfaces.text_splitter_interface import TextSplitterInterface

logger = logging.getLogger(__name__)


class BaseTextSplitter(TextSplitterInterface):
    _max_text_length: int

    def _validate_text(
            self,
            text: str
    ) -> None:
        if not text or not text.strip():
            raise TextSplitterExecutionException("The text cannot be empty or blank.")

        if len(text) > self._max_text_length:
            raise TextSplitterExecutionException("The text exceeds the maximum allowed length.")

    @abstractmethod
    def split_text(
            self,
            text: str
    ) -> list[str]:
        pass
