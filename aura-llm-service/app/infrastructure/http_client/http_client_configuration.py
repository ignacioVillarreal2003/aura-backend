import logging
from dataclasses import dataclass
from typing import Set, Final, FrozenSet

from app.infrastructure.http_client.exceptions.http_client_exceptions import NetworkError, ExternalServiceError

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class HttpClientConfiguration:
    DEFAULT_TIMEOUT: float = 10.0
    DEFAULT_MAX_KEEPALIVE_CONNECTIONS: int = 5
    DEFAULT_MAX_CONNECTIONS: int = 10
    DEFAULT_VERIFY_SSL: bool = True
    DEFAULT_FOLLOW_REDIRECTS: bool = False
    DEFAULT_ENABLE_CIRCUIT_BREAKER: bool = False
    DEFAULT_RETRY_MAX_ATTEMPTS: int = 3
    DEFAULT_RETRY_BASE_DELAY: float = 1.0
    DEFAULT_RETRY_MAX_DELAY: float = 10.0
    DEFAULT_RETRY_EXPONENTIAL_BASE: float = 2.0
    DEFAULT_RETRY_ON_STATUS_CODES: Final[FrozenSet[int]] = frozenset(
        {408, 429, 502, 503, 504}
    )

    timeout: float = DEFAULT_TIMEOUT
    max_keepalive_connections: int = DEFAULT_MAX_KEEPALIVE_CONNECTIONS
    max_connections: int = DEFAULT_MAX_CONNECTIONS
    verify_ssl: bool = DEFAULT_VERIFY_SSL
    follow_redirects: bool = DEFAULT_FOLLOW_REDIRECTS
    enable_circuit_breaker: bool = DEFAULT_ENABLE_CIRCUIT_BREAKER
    retry_max_attempts: int = DEFAULT_RETRY_MAX_ATTEMPTS
    retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY
    retry_max_delay: float = DEFAULT_RETRY_MAX_DELAY
    retry_exponential_base: float = DEFAULT_RETRY_EXPONENTIAL_BASE
    retry_on_status_codes: Set[int] = DEFAULT_RETRY_ON_STATUS_CODES

    def __post_init__(self) -> None:
        try:
            self._validate_all()
            logger.info("HttpClientConfiguration initialized successfully")
        except ValueError as e:
            logger.error(
                "HttpClientConfiguration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(self) -> None:
        self._validate_timeout()
        self._validate_max_keepalive_connections()
        self._validate_max_connections()
        self._validate_retry_max_attempts()
        self._validate_retry_base_delay()
        self._validate_retry_max_delay()
        self._validate_retry_exponential_base()
        self._validate_retry_on_status_codes()

    def _validate_timeout(self) -> None:
        if self.timeout <= 0:
            raise ValueError(
                f"timeout must be positive, got {self.timeout}"
            )

    def _validate_max_connections(self) -> None:
        if self.max_connections <= 0:
            raise ValueError(
                f"max_connections must be positive, got {self.max_connections}"
            )

    def _validate_max_keepalive_connections(self) -> None:
        if self.max_keepalive_connections <= 0:
            raise ValueError(
                f"max_keepalive_connections must be positive, got {self.max_keepalive_connections}"
            )
        if self.max_keepalive_connections > self.max_connections:
            raise ValueError(
                f"max_keepalive_connections ({self.max_keepalive_connections}) cannot be "
                f"greater than max_connections ({self.max_connections})"
            )

    def _validate_retry_max_attempts(self) -> None:
        if self.retry_max_attempts <= 0:
            raise ValueError(
                f"retry_max_attempts must be positive, got {self.retry_max_attempts}"
            )

    def _validate_retry_base_delay(self) -> None:
        if self.retry_base_delay <= 0:
            raise ValueError(
                f"retry_base_delay must be positive, got {self.retry_base_delay}"
            )

    def _validate_retry_max_delay(self) -> None:
        if self.retry_max_delay <= 0:
            raise ValueError(
                f"retry_max_delay must be positive, got {self.retry_max_delay}"
            )

        if self.retry_base_delay > self.retry_max_delay:
            raise ValueError(
                f"retry_base_delay ({self.retry_base_delay}) cannot be greater than "
                f"retry_max_delay ({self.retry_max_delay})"
            )

    def _validate_retry_exponential_base(self) -> None:
        if self.retry_exponential_base <= 1.0:
            raise ValueError(
                f"retry_exponential_base must be greater than 1.0, got {self.retry_exponential_base}"
            )

    def _validate_retry_on_status_codes(self) -> None:
        invalid_codes = {code for code in self.retry_on_status_codes if not (100 <= code <= 599)}
        if invalid_codes:
            raise ValueError(f"retry_on_status_codes contains invalid HTTP status codes: {invalid_codes}")

    def calculate_delay(self,
                        attempt: int) -> float:
        if attempt < 0:
            raise ValueError(f"attempt must be non-negative, got {attempt}")

        delay = self.retry_base_delay * (self.retry_exponential_base ** attempt)
        return min(delay, self.retry_max_delay)

    def should_retry(self, error: Exception, attempt: int) -> bool:
        if attempt < 0 or attempt >= self.retry_max_attempts:
            return False

        if isinstance(error, NetworkError):
            return True

        if isinstance(error, ExternalServiceError):
            return error.status_code in self.retry_on_status_codes

        return False
