import httpx
import logging
import asyncio
from typing import Optional, Any, Dict, Union
from asyncio import Lock
from enum import Enum

from app.infrastructure.http_client.exceptions.http_client_exceptions import (
    HttpClientNotInitializedError,
    ExternalServiceError,
    NetworkError,
    HttpClientInitializationError,
    HttpClientError
)
from app.infrastructure.http_client.circuit_breaker import CircuitBreaker, CircuitBreakerState
from app.infrastructure.http_client.http_method import HttpMethod
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface
from app.infrastructure.http_client.http_client_configuration import HttpClientConfiguration
from app.infrastructure.http_client.retry_configuration import RetryConfiguration
from app.infrastructure.http_client.circuit_breaker_configuration import CircuitBreakerConfiguration

logger = logging.getLogger(__name__)


class HttpClient(HttpClientInterface):
    def __init__(self,
                 configuration: Optional[HttpClientConfiguration] = None) -> None:
        self._configuration = configuration or HttpClientConfiguration()

        self._retry_configuration = self._configuration.retry_configuration or RetryConfiguration()

        self._circuit_breaker: Optional[CircuitBreaker] = None
        if self._configuration.enable_circuit_breaker:
            circuit_breaker_configuration = self._configuration.circuit_breaker_configuration or CircuitBreakerConfiguration()
            self._circuit_breaker = CircuitBreaker(configuration=circuit_breaker_configuration)

        self._client: Optional[httpx.AsyncClient] = None
        self._lock: Lock = Lock()

        logger.info(
            "HttpClient initialized successfully",
            extra={
                "timeout": self._configuration.timeout,
                "max_keepalive_connections": self._configuration.max_keepalive_connections,
                "max_connections": self._configuration.max_connections,
                "verify_ssl": self._configuration.verify_ssl,
                "follow_redirects": self._configuration.follow_redirects,
                "circuit_breaker_enabled": self._configuration.enable_circuit_breaker,
                "retry_max_attempts": self._retry_configuration.max_attempts
            }
        )

    @classmethod
    def with_defaults(cls,
                      timeout: float = 10.0,
                      max_keepalive_connections: int = 5,
                      max_connections: int = 10,
                      verify_ssl: bool = True,
                      follow_redirects: bool = True,
                      enable_circuit_breaker: bool = True,
                      retry_configuration: Optional[RetryConfiguration] = None,
                      circuit_breaker_configuration: Optional[CircuitBreakerConfiguration] = None) -> "HttpClient":
        configuration = HttpClientConfiguration(
            timeout=timeout,
            max_keepalive_connections=max_keepalive_connections,
            max_connections=max_connections,
            verify_ssl=verify_ssl,
            follow_redirects=follow_redirects,
            enable_circuit_breaker=enable_circuit_breaker,
            retry_configuration=retry_configuration,
            circuit_breaker_configuration=circuit_breaker_configuration
        )
        return cls(configuration=configuration)

    async def start(self) -> None:
        async with self._lock:
            if self._client is not None:
                logger.debug("HttpClient already started")
                return

            logger.info("Starting HttpClient connection pool")

            try:
                limits = httpx.Limits(
                    max_keepalive_connections=self._configuration.max_keepalive_connections,
                    max_connections=self._configuration.max_connections
                )

                self._client = httpx.AsyncClient(
                    timeout=self._configuration.timeout,
                    follow_redirects=self._configuration.follow_redirects,
                    limits=limits,
                    verify=self._configuration.verify_ssl
                )

                logger.info(
                    "HttpClient started successfully",
                    extra={
                        "timeout": self._configuration.timeout,
                        "max_keepalive_connections": self._configuration.max_keepalive_connections,
                        "max_connections": self._configuration.max_connections
                    }
                )

            except Exception as e:
                logger.exception(
                    "Failed to initialize HttpClient",
                    extra={
                        "timeout": self._configuration.timeout,
                        "max_keepalive_connections": self._configuration.max_keepalive_connections,
                        "max_connections": self._configuration.max_connections
                    }
                )
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
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    },
                    exc_info=True
                )

            finally:
                self._client = None

    @property
    def is_started(self) -> bool:
        return self._client is not None

    @property
    def configuration(self) -> HttpClientConfiguration:
        return self._configuration

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

        return await self._request_with_retry(
            method,
            url,
            **kwargs
        )

    async def _request_with_retry(self,
                                  method: HttpMethod,
                                  url: str,
                                  **kwargs: Any) -> Any:
        last_error: Optional[Exception] = None

        for attempt in range(self._retry_configuration.max_attempts):
            try:
                return await self._request(method, url, **kwargs)

            except Exception as e:
                last_error = e

                if not self._retry_configuration.should_retry(e, attempt):
                    logger.debug(
                        "Not retrying request after failed attempt",
                        extra={
                            "url": url,
                            "method": method.value,
                            "attempt": attempt + 1,
                            "max_attempts": self._retry_configuration.max_attempts,
                            "error_type": type(e).__name__,
                            "error_message": str(e)
                        }
                    )
                    raise

                if attempt < self._retry_configuration.max_attempts - 1:
                    delay = self._retry_configuration.calculate_delay(attempt)

                    logger.info(
                        "Retrying HTTP request after delay",
                        extra={
                            "url": url,
                            "method": method.value,
                            "attempt": attempt + 1,
                            "max_attempts": self._retry_configuration.max_attempts,
                            "delay_seconds": delay,
                            "error_type": type(e).__name__
                        }
                    )

                    await asyncio.sleep(delay)

        logger.error(
            "All retry attempts exhausted",
            extra={
                "url": url,
                "method": method.value,
                "max_attempts": self._retry_configuration.max_attempts,
                "final_error_type": type(last_error).__name__ if last_error else None
            },
            exc_info=last_error
        )
        raise last_error if last_error else HttpClientError("All retry attempts failed")

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
            "Initiating HTTP request",
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
                    "status_code": response.status_code,
                    "content_length": len(response.content) if response.content else 0
                }
            )

            if response.is_error:
                self._handle_error_response(response, url, method)

            return self._parse_response(response, url, method)

        except httpx.HTTPStatusError as e:
            raise self._handle_http_status_error(e, url, method)

        except httpx.TimeoutException as e:
            logger.error(
                "HTTP request timeout",
                extra={
                    "url": url,
                    "method": method.value,
                    "timeout_seconds": self._configuration.timeout
                },
                exc_info=True
            )
            raise NetworkError(f"Request timeout after {self._configuration.timeout}s") from e

        except httpx.RequestError as e:
            logger.error(
                "Network error during HTTP request",
                extra={
                    "url": url,
                    "method": method.value,
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise NetworkError(f"Network error: {type(e).__name__}") from e

        except Exception as e:
            logger.exception(
                "Unexpected error in HTTP request",
                extra={
                    "url": url,
                    "method": method.value,
                    "error_type": type(e).__name__
                }
            )
            raise HttpClientError(f"Unexpected error: {type(e).__name__}") from e

    def _handle_error_response(self,
                               response: httpx.Response,
                               url: str,
                               method: HttpMethod) -> None:
        logger.warning(
            "External service returned error response",
            extra={
                "url": url,
                "method": method.value,
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
            if isinstance(error_data, dict):
                for field in ["message", "error", "detail", "msg", "description"]:
                    if field in error_data:
                        return str(error_data[field])
            return str(error_data)
        except Exception:
            return response.text or f"HTTP {response.status_code}"

    def _parse_response(self,
                        response: httpx.Response,
                        url: str,
                        method: HttpMethod) -> Union[Dict, list, str, None]:
        if response.status_code == 204:
            logger.debug(
                "Response is 204 No Content",
                extra={
                    "url": url,
                    "method": method.value
                }
            )
            return None

        if not response.content:
            logger.debug(
                "Empty response body",
                extra={
                    "url": url,
                    "method": method.value
                }
            )
            return None

        content_type = response.headers.get("content-type", "").lower()

        if "application/json" in content_type or self._looks_like_json(response.text):
            try:
                return response.json()
            except ValueError as e:
                logger.warning(
                    "Failed to parse response as JSON, returning as text",
                    extra={
                        "url": url,
                        "method": method.value,
                        "content_type": content_type,
                        "error": str(e)
                    }
                )
                return response.text

        logger.debug(
            "Returning response as text",
            extra={
                "url": url,
                "method": method.value,
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
                                  error: httpx.HTTPStatusError,
                                  url: str,
                                  method: HttpMethod) -> ExternalServiceError:
        logger.error(
            "HTTP status error",
            extra={
                "url": url,
                "method": method.value,
                "status_code": error.response.status_code
            },
            exc_info=True
        )

        error_message = self._extract_error_message(error.response)

        return ExternalServiceError(
            status_code=error.response.status_code,
            message=error_message
        )
