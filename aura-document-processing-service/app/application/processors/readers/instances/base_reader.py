import logging
from abc import abstractmethod
from pathlib import Path

from app.application.processors.readers.exceptions.reader_exception import ReaderFileNotFoundException
from app.application.processors.readers.interfaces.reader_interface import ReaderInterface

logger = logging.getLogger(__name__)


class BaseReader(ReaderInterface):
    _max_file_size_bytes: int = 500 * 1024 * 1024

    def _validate_file_exists(
            self,
            file_path: Path
    ) -> None:
        if not file_path.exists():
            raise ReaderFileNotFoundException("The specified file does not exist or cannot be accessed.")

    def _check_magic_bytes(
            self,
            file_path: Path,
            magic: bytes,
            n_bytes: int
    ) -> bool:
        try:
            with open(file_path, "rb") as f:
                return f.read(n_bytes).startswith(magic)
        except Exception as e:
            logger.debug(
                "Failed to read magic bytes from the file.",
                extra={
                    "file_name": file_path.name,
                    "exception_type": type(e).__name__
                }
            )
            return False

    def _validate_file_size(
            self,
            file_path: Path
    ) -> None:
        size = file_path.stat().st_size
        if size == 0:
            raise ReaderFileNotFoundException("The file is empty.")
        if size > self._max_file_size_bytes:
            raise ReaderFileNotFoundException("The file exceeds the maximum allowed size.")

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
