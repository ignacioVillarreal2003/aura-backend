import httpx
import logging
import time
from typing import Optional, Dict, Any, Union
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from aiobreaker import CircuitBreaker, CircuitBreakerError
from datetime import timedelta

from app.infrastructure.http_client.http_client_settings import HttpClientSettings
from app.infrastructure.http_client.exceptions.http_client_exceptions import (
    HttpClientException,
    HttpClientConnectionException,
    HttpClientCircuitBreakerException,
    HttpClientTimeoutException,
    HttpClientNotStartedException
)
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


class HttpClient(HttpClientInterface):
    def __init__(
            self,
            http_client_settings: HttpClientSettings
    ) -> None:
        self._http_client_settings = http_client_settings

        self._client: Optional[httpx.AsyncClient] = None
        self._is_started = False
        self._breaker: Optional[CircuitBreaker] = None

        self._request_count = 0
        self._successful_requests = 0
        self._failed_requests = 0
        self._circuit_breaker_opens = 0
        self._retry_count = 0
        self._total_request_time = 0.0
        self._last_health_check: Optional[Dict[str, Any]] = None

        logger.info(
            "HttpClient initialized",
            extra={
                "timeout": self._http_client_settings.timeout,
                "max_retries": self._http_client_settings.max_retries,
                "circuit_breaker_failures": self._http_client_settings.circuit_breaker_failures
            }
        )

    @classmethod
    def create(
            cls,
            **kwargs
    ) -> "HttpClient":
        http_client_settings = HttpClientSettings(
            **kwargs
        )

        return cls(
            http_client_settings=http_client_settings
        )

    @property
    def settings(
            self
    ) -> HttpClientSettings:
        return self._http_client_settings

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
            logger.error("Attempted to access unstarted HttpClient")
            raise HttpClientNotStartedException("HttpClient not started. Call start() first.")
        return self._client

    async def start(
            self
    ) -> None:
        if self._is_started:
            logger.warning("HttpClient already started")
            return

        logger.info(
            "Starting HttpClient",
            extra={
                "timeout": self.settings.timeout,
                "max_retries": self.settings.max_retries,
                "max_connections": self.settings.max_connections,
            }
        )

        try:
            self._breaker = CircuitBreaker(
                fail_max=self.settings.circuit_breaker_failures,
                timeout_duration=timedelta(
                    seconds=self.settings.circuit_breaker_timeout
                ),
                name="HttpClient"
            )

            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(**self.settings.get_httpx_timeout()),
                limits=httpx.Limits(**self.settings.get_httpx_limits()),
                headers=self.settings.headers,
                verify=self.settings.verify_ssl,
                follow_redirects=self.settings.follow_redirects,
            )

            self._is_started = True
            logger.info("HttpClient started successfully")

        except Exception as e:
            logger.exception("Failed to start HttpClient")
            await self.stop()
            raise HttpClientException(f"Failed to start HTTP client: {str(e)}") from e

    async def stop(
            self
    ) -> None:
        if not self._is_started:
            logger.debug("HttpClient already stopped")
            return

        logger.info("Stopping HttpClient")

        try:
            metrics = self.get_metrics()
            logger.info(
                "Final HttpClient metrics",
                extra=metrics
            )

            if self._client:
                await self._client.aclose()

            self._client = None
            self._breaker = None
            self._is_started = False

            logger.info("HttpClient stopped successfully")

        except Exception as e:
            logger.error(
                "Error stopping HttpClient",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            self._client = None
            self._breaker = None
            self._is_started = False

    def _create_retry_decorator(
            self
    ):
        return retry(
            stop=stop_after_attempt(self.settings.max_retries),
            wait=wait_exponential(
                min=self.settings.retry_backoff_min,
                max=self.settings.retry_backoff_max
            ),
            retry=retry_if_exception_type((
                httpx.TimeoutException,
                httpx.ConnectError,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
                HttpClientTimeoutException,
                HttpClientConnectionException
            )),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

    async def _safe_request(
            self,
            method: str,
            url: str,
            **kwargs
    ) -> httpx.Response:
        retry_decorator = self._create_retry_decorator()

        @retry_decorator
        async def _request():
            start_time = time.time()

            try:
                logger.debug(f"HTTP request: {method} {url}")

                resp = await self.client.request(method, url, **kwargs)
                resp.raise_for_status()

                duration = time.time() - start_time
                self._total_request_time += duration

                logger.debug(
                    f"HTTP response: {method} {url} - "
                    f"Status: {resp.status_code}, Duration: {duration:.3f}s"
                )

                return resp

            except httpx.TimeoutException as e:
                self._retry_count += 1
                logger.warning(f"Timeout on {method} {url}: {e}")
                raise HttpClientTimeoutException(f"Request timeout: {e}") from e

            except (httpx.ConnectError, httpx.NetworkError) as e:
                self._retry_count += 1
                logger.warning(f"Connection error on {method} {url}: {e}")
                raise HttpClientConnectionException(f"Connection failed: {e}") from e

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error on {method} {url}: "
                    f"Status {e.response.status_code}"
                )
                raise HttpClientException(f"HTTP {e.response.status_code}: {e.response.text}") from e

        return await _request()

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
            raise HttpClientNotStartedException("HttpClient not started. Call start() first.")

        self._request_count += 1

        request_headers = {**self.settings.headers, **(headers or {})}

        if timeout:
            kwargs["timeout"] = httpx.Timeout(timeout)

        try:
            response = await self._breaker.call(
                self._safe_request,
                method,
                url,
                params=params,
                json=json,
                data=data,
                headers=request_headers,
                **kwargs
            )

            self._successful_requests += 1
            return response

        except CircuitBreakerError as e:
            self._circuit_breaker_opens += 1
            self._failed_requests += 1
            logger.error(f"Circuit breaker is open for {method} {url}")
            raise HttpClientCircuitBreakerException("Service temporarily unavailable (circuit breaker open)") from e

        except Exception as e:
            self._failed_requests += 1
            logger.error(f"Request failed ({method} {url}): {e}")
            raise

    async def get(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def put(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        return await self.request("PUT", url, **kwargs)

    async def delete(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        return await self.request("DELETE", url, **kwargs)

    async def patch(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        return await self.request("PATCH", url, **kwargs)

    async def health_check(
            self
    ) -> Dict[str, Any]:
        if (not self._is_started or
                not self._client or
                not self._breaker):
            health_data = {
                "status": "unhealthy",
                "started": False,
                "error": "HTTP client not started",
                "timestamp": time.time(),
            }
            self._last_health_check = health_data
            return health_data

        try:
            start_time = time.time()

            _ = self._client.build_request("GET", "http://localhost")

            latency_ms = (time.time() - start_time) * 1000

            avg_request_time = (
                self._total_request_time / self._successful_requests
                if self._successful_requests > 0
                else 0
            )

            health_data = {
                "status": "healthy",
                "started": True,
                "latency_ms": round(latency_ms, 2),
                "timestamp": time.time(),
                "circuit_breaker": {
                    "state": self._breaker.current_state,
                    "failure_count": self._breaker.fail_counter,
                },
                "metrics": self.get_metrics(),
                "performance": {
                    "avg_request_time_ms": round(avg_request_time * 1000, 2),
                    "success_rate": round(
                        (self._successful_requests / self._request_count * 100)
                        if self._request_count > 0
                        else 0,
                        2
                    )
                },
                "settings": {
                    "timeout": self.settings.timeout,
                    "max_retries": self.settings.max_retries,
                    "max_connections": self.settings.max_connections,
                },
            }

            self._last_health_check = health_data
            return health_data

        except Exception as e:
            logger.warning(
                "HttpClient health check failed",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
            health_data = {
                "status": "unhealthy",
                "started": True,
                "error": str(e),
                "timestamp": time.time(),
            }
            self._last_health_check = health_data
            return health_data

    def get_metrics(
            self
    ) -> Dict[str, int]:
        return {
            "request_count": self._request_count,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "circuit_breaker_opens": self._circuit_breaker_opens,
            "retry_count": self._retry_count,
        }

    async def __aenter__(
            self
    ):
        await self.start()
        return self

    async def __aexit__(
            self,
            exc_type,
            exc_val,
            exc_tb
    ):
        await self.stop()
