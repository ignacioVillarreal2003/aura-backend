import logging
from dataclasses import dataclass
from typing import Final

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class CircuitBreakerConfiguration:
    DEFAULT_FAILURE_THRESHOLD: Final[int] = 5
    DEFAULT_RECOVERY_TIMEOUT: Final[float] = 60.0
    DEFAULT_HALF_OPEN_MAX_CALLS: Final[int] = 3

    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT
    half_open_max_calls: int = DEFAULT_HALF_OPEN_MAX_CALLS

    def __post_init__(
            self
    ) -> None:
        try:
            self._validate_all()
            logger.info("CircuitBreakerConfiguration initialized successfully")
        except ValueError as e:
            logger.error(
                "CircuitBreakerConfiguration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(
            self
    ) -> None:
        self._validate_failure_threshold()
        self._validate_recovery_timeout()
        self._validate_half_open_max_calls()

    def _validate_failure_threshold(
            self
    ) -> None:
        if self.failure_threshold <= 0:
            raise ValueError(
                f"failure_threshold must be positive, got {self.failure_threshold}"
            )

    def _validate_recovery_timeout(
            self
    ) -> None:
        if self.recovery_timeout <= 0:
            raise ValueError(
                f"recovery_timeout must be positive, got {self.recovery_timeout}"
            )

    def _validate_half_open_max_calls(
            self
    ) -> None:
        if self.half_open_max_calls <= 0:
            raise ValueError(
                f"half_open_max_calls must be positive, got {self.half_open_max_calls}"
            )
