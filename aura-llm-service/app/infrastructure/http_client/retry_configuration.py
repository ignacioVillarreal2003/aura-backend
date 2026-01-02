from dataclasses import dataclass
from typing import Optional, Set

from app.infrastructure.http_client.exceptions.http_client_exceptions import (
    NetworkError,
    ExternalServiceError
)


@dataclass(frozen=True)
class RetryConfiguration:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    exponential_base: float = 2.0
    retry_on_status_codes: Optional[Set[int]] = None

    def __post_init__(self) -> None:
        self._validate()
        if self.retry_on_status_codes is None:
            object.__setattr__(self, 'retry_on_status_codes', frozenset({
                408,
                429,
                502,
                503,
                504
            }))
        else:
            object.__setattr__(self, 'retry_on_status_codes', frozenset(self.retry_on_status_codes))

    def _validate(self) -> None:
        if self.max_attempts <= 0:
            raise ValueError(
                f"max_attempts must be positive, got {self.max_attempts}"
            )

        if self.base_delay <= 0:
            raise ValueError(
                f"base_delay must be positive, got {self.base_delay}"
            )

        if self.max_delay <= 0:
            raise ValueError(
                f"max_delay must be positive, got {self.max_delay}"
            )

        if self.base_delay > self.max_delay:
            raise ValueError(
                f"base_delay ({self.base_delay}) cannot be greater than "
                f"max_delay ({self.max_delay})"
            )

        if self.exponential_base <= 1.0:
            raise ValueError(
                f"exponential_base must be greater than 1.0, got {self.exponential_base}"
            )

        if self.retry_on_status_codes is not None:
            invalid_codes = {code for code in self.retry_on_status_codes
                             if not (100 <= code <= 599)}
            if invalid_codes:
                raise ValueError(
                    f"retry_on_status_codes contains invalid HTTP status codes: {invalid_codes}"
                )

    def calculate_delay(self,
                        attempt: int) -> float:
        if attempt < 0:
            raise ValueError(f"attempt must be non-negative, got {attempt}")

        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)

    def should_retry(self,
                     error: Exception,
                     attempt: int) -> bool:
        if attempt < 0:
            return False

        if attempt >= self.max_attempts:
            return False

        if isinstance(error, NetworkError):
            return True

        if isinstance(error, ExternalServiceError):
            return error.status_code in self.retry_on_status_codes

        return False
