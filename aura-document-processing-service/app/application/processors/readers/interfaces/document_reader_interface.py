from abc import ABC, abstractmethod
from pathlib import Path


class DocumentReaderInterface(ABC):
    @abstractmethod
    def can_handle(self,
                   file_path: Path) -> bool:
        pass

    @abstractmethod
    def read(self,
             file_path: Path) -> str:
        pass
