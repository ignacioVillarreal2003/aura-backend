from abc import abstractmethod
from pathlib import Path

from app.application.processors.readers.exceptions.reader_exception import ReaderFileNotFoundException
from app.application.processors.readers.interfaces.reader_interface import ReaderInterface

class BaseReader(ReaderInterface):
    def _validate_file_exists(
            self,
            file_path: Path
    ) -> None:
        if not file_path.exists():
            raise ReaderFileNotFoundException("The specified file does not exist or cannot be accessed.")

    @abstractmethod
    def can_handle(
            self,
            file_path: Path
    ) -> bool:
        pass

    @abstractmethod
    def read(
            self,
            file_path: Path
    ) -> str:
        pass
