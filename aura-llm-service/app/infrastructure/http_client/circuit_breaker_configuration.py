from dataclasses import dataclass


@dataclass(frozen=True)
class CircuitBreakerConfiguration:
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.failure_threshold <= 0:
            raise ValueError(
                f"failure_threshold must be positive, got {self.failure_threshold}"
            )

        if self.recovery_timeout <= 0:
            raise ValueError(
                f"recovery_timeout must be positive, got {self.recovery_timeout}"
            )

        if self.half_open_max_calls <= 0:
            raise ValueError(
                f"half_open_max_calls must be positive, got {self.half_open_max_calls}"
            )
