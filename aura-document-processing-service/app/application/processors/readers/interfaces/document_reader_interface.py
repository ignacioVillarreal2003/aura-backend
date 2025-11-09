from abc import ABC, abstractmethod
from pathlib import Path


class DocumentReaderInterface(ABC):
    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        """Determina si este lector puede procesar el archivo."""
        pass

    @abstractmethod
    def read(self, file_path: Path) -> str:
        """Extrae texto del archivo."""
        pass