import logging
from dataclasses import dataclass
from typing import Final

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class DocumentCreationServiceConfiguration:
    MIN_FILE_SIZE_MB: Final[int] = 1
    MAX_FILE_SIZE_MB: Final[int] = 100

    DEFAULT_MAX_FILE_SIZE_MB: Final[int] = 50

    max_file_size_mb: int = DEFAULT_MAX_FILE_SIZE_MB

    def __post_init__(
            self
    ) -> None:
        try:
            self._validate_all()
            logger.info(
                "DocumentCreationServiceConfiguration initialized successfully",
                extra={
                    "max_file_size_mb": self.max_file_size_mb
                }
            )
        except ValueError as e:
            logger.error(
                "Configuration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(
            self
    ) -> None:
        self._validate_max_file_size_mb()

    def _validate_max_file_size_mb(
            self
    ) -> None:
        if not (self.MIN_FILE_SIZE_MB
                <= self.max_file_size_mb
                <= self.MAX_FILE_SIZE_MB):
            raise ValueError(
                f"max_file_size_mb debe estar entre {self.MIN_FILE_SIZE_MB} y {self.MAX_FILE_SIZE_MB}, "
                f"se recibió: {self.max_file_size_mb}"
            )
