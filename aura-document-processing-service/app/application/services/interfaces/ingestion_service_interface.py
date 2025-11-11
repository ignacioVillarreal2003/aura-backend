from typing import Protocol, Optional
from pathlib import Path
from sqlalchemy.orm import Session


class IngestionServiceInterface(Protocol):
    def process_document(self,
                         document_id: int,
                         db: Session,
                         cleaner_type: str = "basic",
                         splitter_type: str = "recursive",
                         split_size: int = 500,
                         split_overlap: int = 50,
                         download_dir: Optional[Path] = None) -> None:
        ...