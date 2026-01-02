import logging
import time
from asyncio import Lock
from typing import Optional, Callable

from app.infrastructure.http_client.circuit_breaker_state import CircuitBreakerState
from app.infrastructure.http_client.exceptions.http_client_exceptions import HttpClientError
from app.infrastructure.http_client.circuit_breaker_configuration import CircuitBreakerConfiguration

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(self,
                 configuration: Optional[CircuitBreakerConfiguration] = None):
        self._configuration = configuration or CircuitBreakerConfiguration()

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = CircuitBreakerState.CLOSED
        self._half_open_calls = 0
        self._lock = Lock()

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    @property
    def configuration(self) -> CircuitBreakerConfiguration:
        return self._configuration

    async def call(self,
                   func: Callable,
                   *args,
                   **kwargs):
        async with self._lock:
            await self._check_and_update_state()

            if self._state == CircuitBreakerState.OPEN:
                logger.warning(
                    "Circuit breaker is OPEN, rejecting request",
                    extra={
                        "failure_count": self._failure_count,
                        "last_failure_time": self._last_failure_time
                    }
                )
                raise HttpClientError("Circuit breaker is open - service unavailable")

            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self._configuration.half_open_max_calls:
                    logger.debug(
                        "Half-open call limit reached",
                        extra={
                            "half_open_calls": self._half_open_calls,
                            "max_calls": self._configuration.half_open_max_calls
                        }
                    )
                    raise HttpClientError("Circuit breaker half-open - limited calls")
                self._half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result

        except Exception as e:
            await self._on_failure()
            raise

    async def _check_and_update_state(self) -> None:
        if self._state == CircuitBreakerState.OPEN:
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time

                if elapsed >= self._configuration.recovery_timeout:
                    logger.info(
                        "Circuit breaker transitioning to HALF_OPEN",
                        extra={
                            "elapsed_time": elapsed,
                            "recovery_timeout": self._configuration.recovery_timeout
                        }
                    )
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._half_open_calls = 0

    async def _on_success(self) -> None:
        async with self._lock:
            previous_state = self._state

            if self._state == CircuitBreakerState.HALF_OPEN:
                logger.info(
                    "Circuit breaker transitioning to CLOSED after successful recovery",
                    extra={
                        "previous_state": previous_state.value,
                        "half_open_calls": self._half_open_calls
                    }
                )
                self._state = CircuitBreakerState.CLOSED

            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            previous_state = self._state

            if self._state == CircuitBreakerState.HALF_OPEN:
                logger.warning(
                    "Circuit breaker transitioning to OPEN after half-open failure",
                    extra={
                        "previous_state": previous_state.value,
                        "failure_count": self._failure_count
                    }
                )
                self._state = CircuitBreakerState.OPEN

            elif self._failure_count >= self._configuration.failure_threshold:
                logger.warning(
                    "Circuit breaker transitioning to OPEN after threshold reached",
                    extra={
                        "previous_state": previous_state.value,
                        "failure_count": self._failure_count,
                        "failure_threshold": self._configuration.failure_threshold
                    }
                )
                self._state = CircuitBreakerState.OPEN
