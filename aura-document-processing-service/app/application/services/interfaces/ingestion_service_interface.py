from pathlib import Path
from typing import Protocol
from sqlalchemy.orm.session import Session

from app.domain.models.document import Document


class IngestionServiceInterface(Protocol):
    def process_document(self,
                         document: Document,
                         db: Session,
                         local_file_path: Path,
                         cleaner_type: str,
                         splitter_type: str,
                         embedder_type: str,
                         split_size: int,
                         split_overlap: int) -> None:
        ...
