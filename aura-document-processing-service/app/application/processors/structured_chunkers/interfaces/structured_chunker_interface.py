from abc import ABC, abstractmethod
from pathlib import Path

from app.application.processors.structured_chunkers.dtos.document_chunk import DocumentChunk


class StructuredChunkerInterface(ABC):
    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """Whether this chunker can process the given file."""

    @abstractmethod
    def chunk_file(self, file_path: Path) -> list[DocumentChunk]:
        """Convert and chunk a document into structure-aware chunks with metadata."""

    @abstractmethod
    def get_chunk_params(self) -> tuple[int | None, int | None]:
        """Return the (chunk_size, chunk_overlap) used, for ingestion traceability."""
