from abc import ABC, abstractmethod
from pathlib import Path
from sqlalchemy.orm.session import Session

from app.domain.models.document import Document


class DocumentIngestionServiceInterface(ABC):
    @abstractmethod
    def execute_document_creation(
            self,
            document: Document,
            db: Session,
            local_file_path: Path
    ) -> None:
        pass
