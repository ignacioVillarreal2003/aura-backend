import httpx
import logging
from typing import Optional, Any, Dict, Union
from asyncio import Lock
from enum import Enum
import asyncio

from app.application.exceptions.http_client_exceptions import (
    HttpClientNotInitializedError,
    ExternalServiceError,
    NetworkError,
    HttpClientInitializationError,
    HttpClientError
)
from app.infrastructure.http_client.circuit_breaker import CircuitBreaker, CircuitBreakerState
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface
from app.infrastructure.http_client.retry_config import RetryConfig

logger = logging.getLogger(__name__)


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class HttpClient(HttpClientInterface):
    DEFAULT_TIMEOUT: float = 10.0
    DEFAULT_MAX_KEEPALIVE: int = 5
    DEFAULT_MAX_CONNECTIONS: int = 10

    def __init__(self,
                 timeout: float = DEFAULT_TIMEOUT,
                 max_keepalive: int = DEFAULT_MAX_KEEPALIVE,
                 max_connections: int = DEFAULT_MAX_CONNECTIONS,
                 verify_ssl: bool = True,
                 retry_config: Optional[RetryConfig] = None,
                 enable_circuit_breaker: bool = True,
                 circuit_breaker_config: Optional[Dict[str, Any]] = None) -> None:
        self._timeout: float = timeout
        self._max_keepalive: int = max_keepalive
        self._max_connections: int = max_connections
        self._verify_ssl: bool = verify_ssl

        self._client: Optional[httpx.AsyncClient] = None
        self._lock: Lock = Lock()

        self._retry_config = retry_config or RetryConfig()

        self._circuit_breaker: Optional[CircuitBreaker] = None
        if enable_circuit_breaker:
            cb_config = circuit_breaker_config or {}
            self._circuit_breaker = CircuitBreaker(**cb_config)

        logger.info(
            "HttpClient configured",
            extra={
                "timeout": timeout,
                "max_keepalive": max_keepalive,
                "max_connections": max_connections,
                "verify_ssl": verify_ssl,
                "retry_enabled": retry_config is not None,
                "circuit_breaker_enabled": enable_circuit_breaker
            }
        )

    async def start(self) -> None:
        async with self._lock:
            if self._client is not None:
                logger.debug("HttpClient already started")
                return

            logger.info("Starting HttpClient connection pool")

            try:
                limits = httpx.Limits(
                    max_keepalive_connections=self._max_keepalive,
                    max_connections=self._max_connections
                )

                self._client = httpx.AsyncClient(
                    timeout=self._timeout,
                    follow_redirects=True,
                    limits=limits,
                    verify=self._verify_ssl
                )

                logger.info("HttpClient started successfully")

            except Exception as e:
                logger.exception("Failed to initialize HttpClient")
                self._client = None
                raise HttpClientInitializationError("Failed to start HTTP client") from e

    async def stop(self) -> None:
        async with self._lock:
            if self._client is None:
                logger.debug("HttpClient already stopped")
                return

            logger.info("Stopping HttpClient connection pool")

            try:
                await self._client.aclose()
                logger.info("HttpClient stopped successfully")

            except Exception as e:
                logger.error(
                    "Error closing HttpClient",
                    exc_info=e
                )

            finally:
                self._client = None

    @property
    def is_started(self) -> bool:
        return self._client is not None

    @property
    def circuit_breaker_state(self) -> Optional[CircuitBreakerState]:
        return self._circuit_breaker.state if self._circuit_breaker else None

    async def get(self,
                  url: str,
                  params: Optional[Dict[str, Any]] = None,
                  headers: Optional[Dict[str, str]] = None,
                  **kwargs: Any) -> Any:
        return await self._request_with_resilience(
            method=HttpMethod.GET,
            url=url,
            params=params,
            headers=headers,
            **kwargs
        )

    async def post(self,
                   url: str,
                   json: Optional[Dict[str, Any]] = None,
                   data: Optional[Any] = None,
                   headers: Optional[Dict[str, str]] = None,
                   **kwargs: Any) -> Any:
        return await self._request_with_resilience(
            method=HttpMethod.POST,
            url=url,
            json=json,
            data=data,
            headers=headers,
            **kwargs
        )

    async def put(self,
                  url: str,
                  json: Optional[Dict[str, Any]] = None,
                  data: Optional[Any] = None,
                  headers: Optional[Dict[str, str]] = None,
                  **kwargs: Any) -> Any:
        return await self._request_with_resilience(
            method=HttpMethod.PUT,
            url=url,
            json=json,
            data=data,
            headers=headers,
            **kwargs
        )

    async def delete(self,
                     url: str,
                     headers: Optional[Dict[str, str]] = None,
                     **kwargs: Any) -> Any:
        return await self._request_with_resilience(
            method=HttpMethod.DELETE,
            url=url,
            headers=headers,
            **kwargs
        )

    async def _request_with_resilience(self,
                                       method: HttpMethod,
                                       url: str,
                                       **kwargs: Any) -> Any:
        if self._circuit_breaker:
            return await self._circuit_breaker.call(
                self._request_with_retry,
                method,
                url,
                **kwargs
            )

        return await self._request_with_retry(method, url, **kwargs)

    async def _request_with_retry(self,
                                  method: HttpMethod,
                                  url: str,
                                  **kwargs: Any) -> Any:
        last_error: Optional[Exception] = None

        for attempt in range(self._retry_config.max_attempts):
            try:
                return await self._request(method, url, **kwargs)

            except Exception as e:
                last_error = e

                if not self._retry_config.should_retry(e, attempt):
                    logger.debug(
                        f"Not retrying after attempt {attempt + 1}",
                        extra={
                            "error": type(e).__name__
                        }
                    )
                    raise

                if attempt < self._retry_config.max_attempts - 1:
                    delay = self._retry_config.calculate_delay(attempt)

                    logger.info(
                        f"Retrying request after {delay:.2f}s (attempt {attempt + 1}/{self._retry_config.max_attempts})",
                        extra={
                            "url": url,
                            "method": method.value,
                            "attempt": attempt + 1,
                            "delay": delay
                        }
                    )

                    await asyncio.sleep(delay)

        logger.error(
            f"All {self._retry_config.max_attempts} retry attempts exhausted",
            extra={
                "url": url,
                "method": method.value
            }
        )
        raise last_error

    def _ensure_client_initialized(self) -> httpx.AsyncClient:
        if self._client is None:
            logger.error("Attempted to use uninitialized HttpClient")
            raise HttpClientNotInitializedError("HttpClient not started. Call start() first.")
        return self._client

    async def _request(self,
                       method: HttpMethod,
                       url: str,
                       **kwargs: Any) -> Any:
        client = self._ensure_client_initialized()

        logger.debug(
            "HTTP request",
            extra={
                "method": method.value,
                "url": url
            }
        )

        try:
            response = await client.request(
                method.value,
                url,
                **kwargs
            )

            logger.debug(
                "HTTP response received",
                extra={
                    "method": method.value,
                    "url": url,
                    "status_code": response.status_code
                }
            )

            if response.is_error:
                self._handle_error_response(response, url)

            return self._parse_response(response, url)

        except httpx.HTTPStatusError as e:
            raise self._handle_http_status_error(e)

        except httpx.TimeoutException as e:
            logger.error(
                "Request timeout",
                extra={
                    "url": url,
                    "timeout": self._timeout
                }
            )
            raise NetworkError(f"Request timeout after {self._timeout}s") from e

        except httpx.RequestError as e:
            logger.error(
                "Network error during request",
                extra={
                    "url": url,
                    "error": str(e)
                }
            )
            raise NetworkError(f"Network error: {type(e).__name__}") from e

        except Exception as e:
            logger.exception(
                "Unexpected error in HTTP request",
                extra={
                    "url": url
                }
            )
            raise HttpClientError(f"Unexpected error: {type(e).__name__}") from e

    def _handle_error_response(self,
                               response: httpx.Response,
                               url: str) -> None:
        logger.warning(
            "External service returned error",
            extra={
                "url": url,
                "status_code": response.status_code,
                "response_preview": response.text[:200] if response.text else None
            }
        )

        error_message = self._extract_error_message(response)

        raise ExternalServiceError(
            status_code=response.status_code,
            message=error_message
        )

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            error_data = response.json()
            for field in ["message", "error", "detail", "msg"]:
                if isinstance(error_data, dict) and field in error_data:
                    return str(error_data[field])
            return str(error_data)
        except Exception:
            return response.text or f"HTTP {response.status_code}"

    def _parse_response(self,
                        response: httpx.Response,
                        url: str) -> Union[Dict, list, str, None]:
        if response.status_code == 204:
            logger.debug("Response is 204 No Content")
            return None

        if not response.content:
            logger.debug("Empty response body")
            return None

        content_type = response.headers.get("content-type", "").lower()

        if "application/json" in content_type or self._looks_like_json(response.text):
            try:
                return response.json()
            except ValueError:
                logger.warning(
                    "Failed to parse response as JSON",
                    extra={
                        "url": url,
                        "content_type": content_type
                    }
                )
                return response.text

        logger.debug(
            "Returning response as text",
            extra={
                "content_type": content_type
            }
        )
        return response.text

    @staticmethod
    def _looks_like_json(text: str) -> bool:
        if not text:
            return False
        stripped = text.strip()
        return (stripped.startswith("{") and stripped.endswith("}")) or \
            (stripped.startswith("[") and stripped.endswith("]"))

    def _handle_http_status_error(self,
                                  error: httpx.HTTPStatusError) -> ExternalServiceError:
        logger.error(
            "HTTP status error",
            extra={
                "status_code": error.response.status_code
            }
        )

        error_message = self._extract_error_message(error.response)

        return ExternalServiceError(
            status_code=error.response.status_code,
            message=error_message
        )


_global_http_client: Optional[HttpClient] = None
_global_http_client_lock: Lock = Lock()


async def get_global_http_client(*,
                                 timeout: float = HttpClient.DEFAULT_TIMEOUT,
                                 max_keepalive: int = HttpClient.DEFAULT_MAX_KEEPALIVE,
                                 max_connections: int = HttpClient.DEFAULT_MAX_CONNECTIONS,
                                 verify_ssl: bool = True,
                                 auto_start: bool = True,
                                 retry_config: Optional[RetryConfig] = None,
                                 enable_circuit_breaker: bool = True) -> HttpClient:
    global _global_http_client

    async with _global_http_client_lock:
        if _global_http_client is None:
            logger.info("Creating global HttpClient singleton")

            _global_http_client = HttpClient(
                timeout=timeout,
                max_keepalive=max_keepalive,
                max_connections=max_connections,
                verify_ssl=verify_ssl,
                retry_config=retry_config,
                enable_circuit_breaker=enable_circuit_breaker
            )

            if auto_start:
                await _global_http_client.start()
                logger.info("Global HttpClient started")

        else:
            logger.debug("Returning existing global HttpClient")

    return _global_http_client


async def shutdown_global_http_client() -> None:
    global _global_http_client

    async with _global_http_client_lock:
        if _global_http_client is not None:
            logger.info("Shutting down global HttpClient")
            await _global_http_client.stop()
            _global_http_client = None
