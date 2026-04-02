import logging
from abc import abstractmethod
from pathlib import Path

from app.application.processors.readers.exceptions.reader_exception import ReaderFileNotFoundException
from app.application.processors.readers.interfaces.reader_interface import ReaderInterface

logger = logging.getLogger(__name__)


class BaseReader(ReaderInterface):
    _max_file_size_bytes: int = 500 * 1024 * 1024

    def _validate_file_exists(self, file_path: Path) -> None:
        if not file_path.exists():
            raise ReaderFileNotFoundException(
                f"The specified file does not exist or cannot be accessed: {file_path.name}"
            )

    def _check_magic_bytes(self, file_path: Path, magic: bytes, n_bytes: int) -> bool:
        try:
            with open(file_path, "rb") as f:
                return f.read(n_bytes).startswith(magic)
        except Exception as e:
            logger.debug(
                "Failed to read magic bytes",
                extra={"file": file_path.name, "error": str(e)},
            )
            return False

    def _validate_file_size(self, file_path: Path) -> None:
        size = file_path.stat().st_size
        if size == 0:
            raise ReaderFileNotFoundException(
                f"The file is empty: {file_path.name}"
            )
        if size > self._max_file_size_bytes:
            raise ReaderFileNotFoundException(
                f"File exceeds maximum allowed size "
                f"({size} > {self._max_file_size_bytes} bytes): {file_path.name}"
            )

    @abstractmethod
    def can_handle(self, file_path: Path) -> bool:
        pass

    @abstractmethod
    def read(self, file_path: Path) -> str:
        pass
