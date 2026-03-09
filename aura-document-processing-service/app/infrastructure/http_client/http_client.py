import logging
import time
from datetime import timedelta
from typing import Any, Callable, Dict, Optional, Union
import httpx
from aiobreaker import CircuitBreaker, CircuitBreakerError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.infrastructure.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientNotStartedException,
    HttpClientTimeoutException
)
from app.infrastructure.http_client.interfaces.http_client_interface import (
    HttpClientInterface
)
from app.infrastructure.http_client.http_client_settings import HttpClientSettings

logger = logging.getLogger(__name__)


class HttpClient(HttpClientInterface):
    def __init__(
            self,
            http_client_settings: Optional[HttpClientSettings] = None
    ) -> None:
        self._http_client_settings = http_client_settings or HttpClientSettings()

        self._client: Optional[httpx.AsyncClient] = None
        self._breaker: Optional[CircuitBreaker] = None
        self._is_started: bool = False

        self._attempt_with_retry: Optional[Callable] = None

        self._request_count: int = 0
        self._successful_requests: int = 0
        self._failed_requests: int = 0
        self._circuit_breaker_opens: int = 0

        self._retry_count: int = 0

        self._total_request_time_ms: float = 0.0

    async def start(self) -> None:
        if self._is_started:
            logger.warning("HttpClient already started — skipping")
            return

        logger.info(
            "Starting HttpClient",
            extra={
                "default_timeout_seconds": self._http_client_settings.default_timeout_seconds,
                "retry_max_attempts": self._http_client_settings.retry_max_attempts,
                "connection_pool_max_size": self._http_client_settings.connection_pool_max_size,
                "ssl_verify_certificates": self._http_client_settings.ssl_verify_certificates
            }
        )

        try:
            self._breaker = CircuitBreaker(
                fail_max=self._http_client_settings.circuit_breaker_failure_threshold,
                timeout_duration=timedelta(
                    seconds=self._http_client_settings.circuit_breaker_recovery_timeout_seconds
                ),
                name="HttpClient"
            )

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(**self._http_client_settings.get_httpx_timeout()),
                limits=httpx.Limits(**self._http_client_settings.get_httpx_limits()),
                headers=self._http_client_settings.merged_request_headers,
                verify=self._http_client_settings.ssl_verify_certificates,
                follow_redirects=self._http_client_settings.follow_http_redirects
            )

            def _on_retry(retry_state) -> None:
                self._retry_count += 1
                logger.warning(
                    "Retrying HTTP request",
                    extra={
                        "attempt": retry_state.attempt_number,
                        "wait_seconds": round(retry_state.next_action.sleep, 2)
                    }
                )

            retry_decorator = retry(
                stop=stop_after_attempt(self._http_client_settings.retry_max_attempts),
                wait=wait_exponential(
                    min=self._http_client_settings.retry_backoff_min_seconds,
                    max=self._http_client_settings.retry_backoff_max_seconds
                ),
                retry=retry_if_exception_type((
                    httpx.TimeoutException,
                    httpx.ConnectError,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                    HttpClientTimeoutException,
                    HttpClientConnectionException
                )),
                before_sleep=_on_retry,
                reraise=True
            )
            self._attempt_with_retry = retry_decorator(self._single_attempt)

            self._is_started = True
            logger.info("HttpClient started successfully")

        except Exception as e:
            logger.exception("Failed to start HttpClient")
            await self.stop()
            raise HttpClientException(f"Failed to start HTTP client: {e}") from e

    async def stop(self) -> None:
        if not self._is_started:
            logger.debug("HttpClient already stopped — skipping")
            return

        logger.info(
            "Stopping HttpClient",
            extra=self.get_metrics()
        )

        try:
            if self._client:
                await self._client.aclose()
        except Exception:
            logger.exception("Error closing HttpClient connections")
        finally:
            self._client = None
            self._breaker = None
            self._attempt_with_retry = None
            self._is_started = False

        logger.info("HttpClient stopped successfully")

    @property
    def is_started(self) -> bool:
        return self._is_started

    @property
    def client(self) -> httpx.AsyncClient:
        if (not self._is_started
                or not self._client):
            raise HttpClientNotStartedException("HttpClient is not started. Call start() first.")
        return self._client

    async def request(
            self,
            method: str,
            url: str,
            params: Optional[Dict[str, Any]] = None,
            json: Optional[Dict[str, Any]] = None,
            data: Optional[Union[Dict[str, Any], bytes]] = None,
            headers: Optional[Dict[str, str]] = None,
            timeout: Optional[float] = None,
            **kwargs
    ) -> httpx.Response:
        if not self._is_started or not self._client or not self._breaker:
            raise HttpClientNotStartedException("HttpClient is not started. Call start() first.")

        self._request_count += 1

        if headers is not None:
            kwargs["headers"] = headers

        if timeout is not None:
            kwargs["timeout"] = httpx.Timeout(timeout)

        try:
            response = await self._breaker.call(
                self._attempt_with_retry,
                method,
                url,
                params=params,
                json=json,
                data=data,
                **kwargs
            )

            self._successful_requests += 1
            return response

        except CircuitBreakerError as e:
            self._circuit_breaker_opens += 1
            self._failed_requests += 1
            logger.error(
                "Circuit breaker is open — request rejected",
                extra={
                    "method": method,
                    "url": url
                }
            )
            raise HttpClientCircuitBreakerException("Service temporarily unavailable (circuit breaker open)") from e

        except (
                HttpClientTimeoutException,
                HttpClientConnectionException
        ):
            self._failed_requests += 1
            raise

        except Exception:
            self._failed_requests += 1
            raise

    async def get(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        return await self.request(
            "GET",
            url,
            **kwargs
        )

    async def post(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        return await self.request(
            "POST",
            url,
            **kwargs
        )

    async def put(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        return await self.request(
            "PUT",
            url,
            **kwargs
        )

    async def patch(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        return await self.request(
            "PATCH",
            url,
            **kwargs
        )

    async def delete(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        return await self.request(
            "DELETE",
            url,
            **kwargs
        )

    async def health_check(self) -> Dict[str, Any]:
        if (not self._is_started
                or not self._client
                or not self._breaker):
            return {
                "status": "unhealthy",
                "started": False,
                "error": "HTTP client not started",
            }

        breaker_state = str(self._breaker.current_state)
        is_healthy = breaker_state == "closed"

        return {
            "status": "healthy" if is_healthy else "degraded",
            "started": True,
            "circuit_breaker": {
                "state": breaker_state,
                "failure_count": self._breaker.fail_counter,
                "failure_threshold": self._http_client_settings.circuit_breaker_failure_threshold
            },
            "metrics": self.get_metrics(),
            "settings": {
                "default_timeout_seconds": self._http_client_settings.default_timeout_seconds,
                "retry_max_attempts": self._http_client_settings.retry_max_attempts,
                "connection_pool_max_size": self._http_client_settings.connection_pool_max_size,
                "ssl_verify_certificates": self._http_client_settings.ssl_verify_certificates
            }
        }

    def get_metrics(self) -> Dict[str, Any]:
        total = self._request_count
        avg_request_time_ms = (
            round(self._total_request_time_ms / self._successful_requests, 2)
            if self._successful_requests > 0
            else 0.0
        )
        success_rate = (
            round(self._successful_requests / total, 4)
            if total > 0
            else 1.0
        )

        return {
            "request_count": self._request_count,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "circuit_breaker_opens": self._circuit_breaker_opens,
            "retry_count": self._retry_count,
            "success_rate": success_rate,
            "avg_request_time_ms": avg_request_time_ms
        }

    async def __aenter__(self) -> "HttpClient":
        await self.start()
        return self

    async def __aexit__(
            self,
            exc_type,
            exc_val,
            exc_tb
    ) -> None:
        await self.stop()

    async def _single_attempt(
            self,
            method: str,
            url: str,
            **kwargs
    ) -> httpx.Response:
        start_time = time.monotonic()

        try:
            logger.debug(
                "Executing HTTP request",
                extra={
                    "method": method,
                    "url": url
                }
            )

            response = await self.client.request(
                method,
                url,
                **kwargs
            )
            response.raise_for_status()

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            self._total_request_time_ms += elapsed_ms

            logger.debug(
                "HTTP request completed",
                extra={
                    "method": method,
                    "url": url,
                    "status_code": response.status_code,
                    "elapsed_ms": elapsed_ms
                }
            )

            return response

        except httpx.TimeoutException as e:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            self._total_request_time_ms += elapsed_ms
            logger.warning(
                "HTTP request timed out",
                extra={
                    "method": method,
                    "url": url,
                    "elapsed_ms": elapsed_ms
                }
            )
            raise HttpClientTimeoutException(f"Request timed out: {e}") from e

        except (
                httpx.ConnectError,
                httpx.NetworkError
        ) as e:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            self._total_request_time_ms += elapsed_ms
            logger.warning(
                "HTTP connection error",
                extra={
                    "method": method,
                    "url": url,
                    "elapsed_ms": elapsed_ms
                }
            )
            raise HttpClientConnectionException(f"Connection failed: {e}") from e

        except httpx.HTTPStatusError as e:
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            self._total_request_time_ms += elapsed_ms
            logger.error(
                "HTTP error response",
                extra={
                    "method": method,
                    "url": url,
                    "status_code": e.response.status_code,
                    "elapsed_ms": elapsed_ms
                }
            )
            raise HttpClientException(
                f"HTTP {e.response.status_code}: {e.response.text}",
                status_code=e.response.status_code
            ) from e
