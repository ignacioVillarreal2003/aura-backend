import asyncio
import logging
import time
from datetime import timedelta
from typing import Any, Callable, Optional, Union
from urllib.parse import urlparse
import httpx
from aiobreaker import CircuitBreaker, CircuitBreakerError
from fastapi import HTTPException, Request, status
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.infrastructure.http.http_client.exceptions.http_client_exceptions import (
    HttpClientCircuitBreakerException,
    HttpClientConnectionException,
    HttpClientException,
    HttpClientNotStartedException,
    HttpClientTimeoutException
)
from app.infrastructure.http.http_client.http_client_settings import HttpClientSettings
from app.infrastructure.http.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


class HttpClient(HttpClientInterface):
    def __init__(
            self,
            http_client_settings: Optional[HttpClientSettings] = None
    ) -> None:
        self._settings = http_client_settings or HttpClientSettings()

        self._client: Optional[httpx.AsyncClient] = None
        self._breaker: Optional[CircuitBreaker] = None
        self._attempt_with_retry: Optional[Callable] = None
        self._is_started: bool = False

        self._lifecycle_lock = asyncio.Lock()

    @staticmethod
    def _request_log_context(
            method: str,
            url: str
    ) -> dict[str, Any]:
        parsed = urlparse(url)
        return {
            "method": method,
            "http_host": parsed.netloc or None,
            "path": parsed.path if parsed.path else "/"
        }

    async def start(
            self
    ) -> None:
        async with self._lifecycle_lock:
            if self._is_started:
                logger.debug("The HTTP client is already running; skipping start.")
                return

            logger.info(
                "Starting the shared HTTP client.",
                extra={
                    "timeout_seconds": self._settings.timeout_seconds,
                    "retry_max_attempts": self._settings.retry_max_attempts,
                    "connection_pool_max_size": self._settings.connection_pool_max_size,
                    "ssl_verify_certificates": self._settings.ssl_verify_certificates
                }
            )

            try:
                self._breaker = CircuitBreaker(
                    fail_max=self._settings.circuit_breaker_failure_threshold,
                    timeout_duration=timedelta(
                        seconds=self._settings.circuit_breaker_recovery_timeout_seconds
                    ),
                    name="HttpClient"
                )

                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        self._settings.timeout_seconds,
                        **self._settings.get_httpx_timeout(),
                    ),
                    limits=httpx.Limits(**self._settings.get_httpx_limits()),
                    headers=self._settings.merged_request_headers,
                    verify=self._settings.ssl_verify_certificates,
                    follow_redirects=self._settings.follow_http_redirects
                )

                def _on_retry(
                        retry_state
                ) -> None:
                    logger.warning(
                        "Retrying an outbound HTTP request after a transient failure.",
                        extra={
                            "attempt": retry_state.attempt_number,
                            "wait_seconds": round(retry_state.next_action.sleep, 2)
                        }
                    )

                retry_decorator = retry(
                    stop=stop_after_attempt(self._settings.retry_max_attempts),
                    wait=wait_exponential(
                        min=self._settings.retry_backoff_min_seconds,
                        max=self._settings.retry_backoff_max_seconds
                    ),
                    retry=retry_if_exception_type(
                        (
                            httpx.TimeoutException,
                            httpx.ConnectError,
                            httpx.NetworkError,
                            httpx.RemoteProtocolError,
                            HttpClientTimeoutException,
                            HttpClientConnectionException
                        )
                    ),
                    before_sleep=_on_retry,
                    reraise=True
                )
                self._attempt_with_retry = retry_decorator(self._single_attempt)

                self._is_started = True
                logger.info("The shared HTTP client started successfully.")

            except Exception as e:
                await self._cleanup_resources()
                logger.exception("The HTTP client failed to start.")
                raise HttpClientException(
                    "Failed to start the HTTP client.",
                    status_code=503
                ) from e

    async def stop(
            self
    ) -> None:
        async with self._lifecycle_lock:
            if not self._is_started:
                logger.debug("The HTTP client is already stopped; nothing to do.")
                return

            logger.info("Stopping the shared HTTP client.")
            await self._cleanup_resources()
            logger.info("The shared HTTP client stopped successfully.")

    @property
    def is_started(
            self
    ) -> bool:
        return self._is_started

    @property
    def client(
            self
    ) -> httpx.AsyncClient:
        if not self._is_started or not self._client:
            raise HttpClientNotStartedException("The HTTP client is not started; call start() first.")
        return self._client

    async def request(
            self,
            method: str,
            url: str,
            params: Optional[dict[str, Any]] = None,
            json: Optional[dict[str, Any]] = None,
            data: Optional[Union[dict[str, Any], bytes]] = None,
            headers: Optional[dict[str, str]] = None,
            timeout: Optional[float] = None,
            **kwargs
    ) -> httpx.Response:
        if not self._is_started or not self._client or not self._breaker:
            raise HttpClientNotStartedException("The HTTP client is not started; call start() first.")

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
            return response

        except CircuitBreakerError as e:
            log_ctx = self._request_log_context(method, url)
            logger.error(
                "The circuit breaker is open; this outbound request was not sent.",
                extra=log_ctx
            )
            raise HttpClientCircuitBreakerException(
                "The service is temporarily unavailable because the circuit breaker is open."
            ) from e

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

    async def health_check(
            self
    ) -> dict[str, Any]:
        if not self._is_started or not self._client or not self._breaker:
            return {
                "status": "unhealthy",
                "started": False,
                "error": "HTTP client not started"
            }

        breaker_state = str(self._breaker.current_state)
        is_healthy = breaker_state == "closed"

        return {
            "status": "healthy" if is_healthy else "degraded",
            "started": True,
            "circuit_breaker": {
                "state": breaker_state,
                "failure_count": self._breaker.fail_counter,
                "failure_threshold": self._settings.circuit_breaker_failure_threshold
            },
            "settings": {
                "timeout_seconds": self._settings.timeout_seconds,
                "retry_max_attempts": self._settings.retry_max_attempts,
                "connection_pool_max_size": self._settings.connection_pool_max_size,
                "ssl_verify_certificates": self._settings.ssl_verify_certificates
            }
        }

    async def __aenter__(
            self
    ) -> "HttpClient":
        await self.start()
        return self

    async def __aexit__(
            self,
            exc_type,
            exc_val,
            exc_tb
    ) -> None:
        await self.stop()

    async def _cleanup_resources(
            self
    ) -> None:
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                logger.exception("An error occurred while closing HTTP client connections.")

        self._client = None
        self._breaker = None
        self._attempt_with_retry = None
        self._is_started = False

    async def _single_attempt(
            self,
            method: str,
            url: str,
            **kwargs
    ) -> httpx.Response:
        start_time = time.monotonic()
        log_ctx = self._request_log_context(method, url)

        try:
            logger.debug(
                "Sending an outbound HTTP request.",
                extra=log_ctx
            )

            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()

            elapsed_ms = self._record_elapsed(start_time)
            logger.debug(
                "Outbound HTTP request completed successfully.",
                extra={
                    **log_ctx,
                    "status_code": response.status_code,
                    "elapsed_ms": elapsed_ms
                }
            )
            return response

        except httpx.TimeoutException as e:
            elapsed_ms = self._record_elapsed(start_time)
            logger.warning(
                "The outbound HTTP request timed out.",
                extra={
                    **log_ctx,
                    "elapsed_ms": elapsed_ms
                }
            )
            raise HttpClientTimeoutException("The request timed out.") from e

        except (
                httpx.ConnectError,
                httpx.NetworkError
        ) as e:
            elapsed_ms = self._record_elapsed(start_time)
            logger.warning(
                "Could not reach the remote service for this HTTP request.",
                extra={
                    **log_ctx,
                    "elapsed_ms": elapsed_ms
                }
            )
            raise HttpClientConnectionException("Could not reach the remote service.") from e

        except httpx.HTTPStatusError as e:
            elapsed_ms = self._record_elapsed(start_time)
            status_code = e.response.status_code
            logger.error(
                "The remote service returned an error HTTP status.",
                extra={
                    **log_ctx,
                    "status_code": status_code,
                    "elapsed_ms": elapsed_ms
                }
            )
            raise HttpClientException(
                "Upstream service returned an error response.",
                status_code=status_code
            ) from e

    @staticmethod
    def _record_elapsed(
            start_time: float
    ) -> float:
        return round((time.monotonic() - start_time) * 1000, 2)


async def get_http_client(
        request: Request
) -> HttpClientInterface:
    try:
        http_client: HttpClientInterface = request.app.state.http_client
        if not http_client.is_started:
            logger.error("The HTTP client exists on the application but has not been started.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="HttpClient is not available"
            )
        return http_client
    except AttributeError:
        logger.error("The HTTP client was not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="HttpClient is not configured"
        )
