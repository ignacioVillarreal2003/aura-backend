from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings


class TextSplitterInterface(ABC):
    @abstractmethod
    def __init__(self, text_splitter_settings: "TextSplitterSettings") -> None:
        ...

    @abstractmethod
    def split_text(
            self,
            text: str
    ) -> list[str]:
        pass

    def get_chunk_params(self) -> tuple[int | None, int | None]:
        """Return the (chunk_size, chunk_overlap) used, for ingestion traceability."""
        return None, None
