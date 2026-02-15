from abc import ABC, abstractmethod
from typing import Dict
from pathlib import Path

from app.domain.models.document import Document


class DocumentIngestionServiceInterface(ABC):
    @abstractmethod
    async def process_document(
            self,
            document: Document,
            local_file_path: Path
    ) -> None:
        pass

    @abstractmethod
    def get_metrics(
            self
    ) -> Dict[str, int]:
        pass
