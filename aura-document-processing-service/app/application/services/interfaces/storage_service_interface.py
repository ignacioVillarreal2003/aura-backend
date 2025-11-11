from typing import Protocol
from pathlib import Path


class StorageServiceInterface(Protocol):
    def download_document(self,
                          object_name: str,
                          destination_dir: Path | None = None) -> Path:
        ...