from abc import ABC, abstractmethod
from pathlib import Path
from sqlalchemy.orm.session import Session

from app.domain.models.document import Document


class DocumentIngestionServiceInterface(ABC):
    @abstractmethod
    def process_document(
            self,
            document: Document,
            local_file_path: Path
    ) -> None:
        pass
