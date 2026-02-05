import logging
from dataclasses import dataclass
from typing import Final, Tuple

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class DocumentContextProviderConfiguration:
    MAX_CHARS_PER_FRAGMENTS: Final[Tuple[int, int]] = (1_000, 100_000)
    MAX_FRAGMENTS_TOTAL: Final[Tuple[int, int]] = (3, 30)
    MAX_TOTAL_CHARS: Final[Tuple[int, int]] = (10_000, 1_000_000)

    DEFAULT_MAX_CHARS_PER_FRAGMENTS: Final[int] = 10_000
    DEFAULT_TRUNCATE_FRAGMENTS_EXCEEDING_MAX_CHARS: Final[bool] = False
    DEFAULT_MAX_FRAGMENTS_TOTAL: Final[int] = 6
    DEFAULT_MAX_RESPONSE_SIZE_CHARS: Final[int] = 500_000

    max_chars_per_fragment: int = DEFAULT_MAX_CHARS_PER_FRAGMENTS
    truncate_fragments_exceeding_max_chars: bool = DEFAULT_TRUNCATE_FRAGMENTS_EXCEEDING_MAX_CHARS
    max_fragments_total: int = DEFAULT_MAX_FRAGMENTS_TOTAL
    max_total_chars: int = DEFAULT_MAX_RESPONSE_SIZE_CHARS

    def __post_init__(
            self
    ) -> None:
        try:
            self._validate_all()
            logger.info("DocumentContextProviderConfiguration initialized successfully")
        except ValueError as e:
            logger.error(
                "DocumentContextProviderConfiguration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(
            self
    ) -> None:
        self._validate_max_chars_per_fragment()
        self._validate_max_fragments_total()
        self._validate_max_total_chars()

    def _validate_max_chars_per_fragment(
            self
    ) -> None:
        if not (self.MAX_CHARS_PER_FRAGMENTS[0]
                <= self.max_chars_per_fragment
                <= self.MAX_CHARS_PER_FRAGMENTS[1]):
            raise ValueError(
                f"max_chars_per_fragment debe estar entre {self.MAX_CHARS_PER_FRAGMENTS[0]} y {self.MAX_CHARS_PER_FRAGMENTS[1]}, "
                f"se recibió: {self.max_chars_per_fragment}"
            )

    def _validate_max_fragments_total(
            self
    ) -> None:
        if not (self.MAX_FRAGMENTS_TOTAL[0]
                <= self.max_fragments_total
                <= self.MAX_FRAGMENTS_TOTAL[1]):
            raise ValueError(
                f"max_fragments_total debe estar entre "
                f"{self.MAX_FRAGMENTS_TOTAL[0]} y {self.MAX_FRAGMENTS_TOTAL[1]}, "
                f"se recibió: {self.max_fragments_total}"
            )

    def _validate_max_total_chars(
            self
    ) -> None:
        if not (self.MAX_TOTAL_CHARS[0]
                <= self.max_total_chars
                <= self.MAX_TOTAL_CHARS[1]):
            raise ValueError(
                f"max_total_chars debe estar entre {self.MAX_TOTAL_CHARS[0]} y {self.MAX_TOTAL_CHARS[1]}, "
                f"se recibió: {self.max_total_chars}"
            )
