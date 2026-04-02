from abc import ABC, abstractmethod
from pathlib import Path

from app.domain.models.document import Document


class DocumentIngestionServiceInterface(ABC):
    @abstractmethod
    async def process_document(
            self,
            document: Document,
            local_file_path: Path,
            prefer_docling: bool = False,
    ) -> None:
        pass
