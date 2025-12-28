import logging
from asyncio import Lock
from enum import Enum
from typing import Optional, Callable

from app.infrastructure.http_client.exceptions.http_client_exceptions import HttpClientError

logger = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 half_open_max_calls: int = 3):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = CircuitBreakerState.CLOSED
        self._half_open_calls = 0
        self._lock = Lock()

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    async def call(self,
                   func: Callable,
                   *args,
                   **kwargs):
        async with self._lock:
            await self._check_and_update_state()

            if self._state == CircuitBreakerState.OPEN:
                logger.warning("Circuit breaker is OPEN, rejecting request")
                raise HttpClientError("Circuit breaker is open - service unavailable")

            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self._half_open_max_calls:
                    logger.debug("Half-open call limit reached")
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
                import time
                elapsed = time.time() - self._last_failure_time

                if elapsed >= self._recovery_timeout:
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._half_open_calls = 0

    async def _on_success(self) -> None:
        async with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                logger.info("Circuit breaker transitioning to CLOSED after successful recovery")
                self._state = CircuitBreakerState.CLOSED

            self._failure_count = 0
            self._last_failure_time = None

    async def _on_failure(self) -> None:
        import time

        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitBreakerState.HALF_OPEN:
                logger.warning("Circuit breaker transitioning to OPEN after half-open failure")
                self._state = CircuitBreakerState.OPEN

            elif self._failure_count >= self._failure_threshold:
                logger.warning(f"Circuit breaker transitioning to OPEN after {self._failure_count} failures")
                self._state = CircuitBreakerState.OPEN
