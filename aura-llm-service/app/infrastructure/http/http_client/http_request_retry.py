import logging
from typing import Awaitable, Callable, TypeVar
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientConnectionException,
    HttpClientServerException,
    HttpClientTimeoutException,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_REQUEST_EXCEPTIONS: tuple[type[Exception], ...] = (
    HttpClientTimeoutException,
    HttpClientConnectionException,
    HttpClientServerException,
)


async def retry_idempotent_request(
        operation: Callable[[], Awaitable[T]],
        *,
        max_attempts: int,
        min_wait: float,
        max_wait: float,
) -> T:
    async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(min=min_wait, max=max_wait),
            retry=retry_if_exception_type(RETRYABLE_REQUEST_EXCEPTIONS),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
    ):
        with attempt:
            return await operation()
    raise AssertionError("unreachable: AsyncRetrying always returns a value or re-raises")
