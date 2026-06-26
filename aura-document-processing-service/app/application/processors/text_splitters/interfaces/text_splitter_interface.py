from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from app.application.processors.text_splitters.dtos.document_chunk import DocumentChunk

if TYPE_CHECKING:
    from app.application.processors.text_splitters.text_splitter_settings import TextSplitterSettings


class TextSplitterInterface(ABC):
    @abstractmethod
    def __init__(self, text_splitter_settings: "TextSplitterSettings") -> None:
        pass

    def supports(self, file_path: Path) -> bool:
        return True

    def split_text(self, text: str) -> list[DocumentChunk]:
        raise NotImplementedError("This splitter does not support text-based splitting.")

    def chunk_file(self, file_path: Path) -> list[DocumentChunk]:
        raise NotImplementedError("This splitter does not support file-based chunking.")

    def get_chunk_params(self) -> tuple[int | None, int | None]:
        return None, None
