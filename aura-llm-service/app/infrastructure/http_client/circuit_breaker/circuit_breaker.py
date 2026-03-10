import logging
import time
from asyncio import Lock
from typing import Optional, Callable, Any

from app.infrastructure.http_client.constants.circuit_breaker_state import CircuitBreakerState
from app.infrastructure.http_client.exceptions.http_client_exceptions import HttpClientError
from app.infrastructure.http_client.circuit_breaker.circuit_breaker_configuration import CircuitBreakerConfiguration

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(
            self,
            circuit_breaker_configuration: CircuitBreakerConfiguration
    ) -> None:
        self._circuit_breaker_configuration = circuit_breaker_configuration

        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = CircuitBreakerState.CLOSED
        self._half_open_calls = 0
        self._lock = Lock()

    @classmethod
    def create(
            cls,
            failure_threshold: Optional[int] = None,
            recovery_timeout: Optional[float] = None,
            half_open_max_calls: Optional[int] = None
    ) -> "CircuitBreaker":
        config_kwargs = {}

        if failure_threshold is not None:
            config_kwargs['failure_threshold'] = failure_threshold
        if recovery_timeout is not None:
            config_kwargs['recovery_timeout'] = recovery_timeout
        if half_open_max_calls is not None:
            config_kwargs['half_open_max_calls'] = half_open_max_calls

        circuit_breaker_configuration = CircuitBreakerConfiguration(**config_kwargs)

        return cls(
            circuit_breaker_configuration=circuit_breaker_configuration
        )

    @property
    def state(
            self
    ) -> CircuitBreakerState:
        return self._state

    async def call(
            self,
            func: Callable,
            *args: Any,
            **kwargs: Any
    ) -> Any:
        async with self._lock:
            self._check_and_update_state()

            if self._state == CircuitBreakerState.OPEN:
                logger.warning("Circuit breaker is OPEN, rejecting request")
                raise HttpClientError("Circuit breaker is open - service unavailable")

            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self._circuit_breaker_configuration.half_open_max_calls:
                    logger.debug("Half-open call limit reached")
                    raise HttpClientError("Circuit breaker half-open - limited calls")
                self._half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result

        except Exception:
            await self._on_failure()
            raise

    def _check_and_update_state(
            self
    ) -> None:
        if self._state == CircuitBreakerState.OPEN and self._last_failure_time:
            elapsed = time.time() - self._last_failure_time

            if elapsed >= self._circuit_breaker_configuration.recovery_timeout:
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                self._state = CircuitBreakerState.HALF_OPEN
                self._half_open_calls = 0

    async def _on_success(
            self
    ) -> None:
        async with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                logger.info("Circuit breaker transitioning to CLOSED after successful recovery")
                self._state = CircuitBreakerState.CLOSED

            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0

    async def _on_failure(
            self
    ) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitBreakerState.HALF_OPEN:
                logger.warning("Circuit breaker transitioning to OPEN after half-open failure")
                self._state = CircuitBreakerState.OPEN
                self._half_open_calls = 0

            elif self._failure_count >= self._circuit_breaker_configuration.failure_threshold:
                logger.warning("Circuit breaker transitioning to OPEN after threshold reached")
                self._state = CircuitBreakerState.OPEN
