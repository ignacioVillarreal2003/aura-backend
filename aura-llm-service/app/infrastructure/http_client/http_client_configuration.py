from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from app.infrastructure.http_client.retry_configuration import RetryConfiguration

if TYPE_CHECKING:
    from app.infrastructure.http_client.circuit_breaker_configuration import CircuitBreakerConfiguration


@dataclass(frozen=True)
class HttpClientConfiguration:
    timeout: float = 10.0
    max_keepalive_connections: int = 5
    max_connections: int = 10
    verify_ssl: bool = True
    follow_redirects: bool = True

    retry_configuration: Optional[RetryConfiguration] = None
    circuit_breaker_configuration: Optional["CircuitBreakerConfiguration"] = None
    enable_circuit_breaker: bool = True

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if self.timeout <= 0:
            raise ValueError(
                f"timeout must be positive, got {self.timeout}"
            )

        if self.max_keepalive_connections <= 0:
            raise ValueError(
                f"max_keepalive_connections must be positive, got {self.max_keepalive_connections}"
            )

        if self.max_connections <= 0:
            raise ValueError(
                f"max_connections must be positive, got {self.max_connections}"
            )

        if self.max_keepalive_connections > self.max_connections:
            raise ValueError(
                f"max_keepalive_connections ({self.max_keepalive_connections}) cannot be "
                f"greater than max_connections ({self.max_connections})"
            )
