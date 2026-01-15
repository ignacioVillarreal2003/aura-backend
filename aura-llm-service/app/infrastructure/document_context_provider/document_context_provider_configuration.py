import logging
from dataclasses import dataclass
from typing import Final

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class DocumentContextProviderConfiguration:
    MIN_FRAGMENT_CHARS: Final[int] = 1
    MAX_FRAGMENT_CHARS: Final[int] = 100_000

    MIN_TOTAL_FRAGMENTS_IN_RESPONSE: Final[int] = 1
    MAX_TOTAL_FRAGMENTS_IN_RESPONSE: Final[int] = 1_000

    MIN_RESPONSE_SIZE_CHARS: Final[int] = 1
    MAX_RESPONSE_SIZE_CHARS: Final[int] = 1_000_000

    DEFAULT_MAX_FRAGMENT_CHARS: Final[int] = 10_000
    DEFAULT_TRUNCATE_OVERSIZED_FRAGMENTS: Final[bool] = False
    DEFAULT_MAX_TOTAL_FRAGMENTS_IN_RESPONSE: Final[int] = 100
    DEFAULT_MAX_RESPONSE_SIZE_CHARS: Final[int] = 500_000

    max_fragment_chars: int = DEFAULT_MAX_FRAGMENT_CHARS
    truncate_oversized_fragments: bool = DEFAULT_TRUNCATE_OVERSIZED_FRAGMENTS
    max_total_fragments_in_response: int = DEFAULT_MAX_TOTAL_FRAGMENTS_IN_RESPONSE
    max_response_size_chars: int = DEFAULT_MAX_RESPONSE_SIZE_CHARS

    def __post_init__(self) -> None:
        try:
            self._validate_all()
            logger.info(
                "ContextProviderConfiguration initialized successfully",
                extra={
                    "max_fragment_chars": self.max_fragment_chars,
                    "truncate_oversized_fragments": self.truncate_oversized_fragments,
                    "max_total_fragments_in_response": self.max_total_fragments_in_response,
                    "max_response_size_chars": self.max_response_size_chars
                }
            )
        except ValueError as e:
            logger.error(
                "ContextProviderConfiguration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(self) -> None:
        self._validate_max_fragment_chars()
        self._validate_max_total_fragments_in_response()
        self._validate_max_response_size_chars()

    def _validate_max_fragment_chars(self) -> None:
        if not (self.MIN_FRAGMENT_CHARS
                <= self.max_fragment_chars
                <= self.MAX_FRAGMENT_CHARS):
            raise ValueError(
                f"max_fragment_chars debe estar entre {self.MIN_FRAGMENT_CHARS} y {self.MAX_FRAGMENT_CHARS}, "
                f"se recibió: {self.max_fragment_chars}"
            )

    def _validate_max_total_fragments_in_response(self) -> None:
        if not (self.MIN_TOTAL_FRAGMENTS_IN_RESPONSE
                <= self.max_total_fragments_in_response
                <= self.MAX_TOTAL_FRAGMENTS_IN_RESPONSE):
            raise ValueError(
                f"max_total_fragments_in_response debe estar entre "
                f"{self.MIN_TOTAL_FRAGMENTS_IN_RESPONSE} y {self.MAX_TOTAL_FRAGMENTS_IN_RESPONSE}, "
                f"se recibió: {self.max_total_fragments_in_response}"
            )

    def _validate_max_response_size_chars(self) -> None:
        if not (self.MIN_RESPONSE_SIZE_CHARS
                <= self.max_response_size_chars
                <= self.MAX_RESPONSE_SIZE_CHARS):
            raise ValueError(
                f"max_response_size_chars debe estar entre {self.MIN_RESPONSE_SIZE_CHARS} y {self.MAX_RESPONSE_SIZE_CHARS}, "
                f"se recibió: {self.max_response_size_chars}"
            )
