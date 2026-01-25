import httpx
import logging
import asyncio
from typing import Optional, Any, Dict, Union, Set
from asyncio import Lock

from app.infrastructure.http_client.exceptions.http_client_exceptions import (
    HttpClientNotInitializedError,
    ExternalServiceError,
    NetworkError,
    HttpClientInitializationError,
    HttpClientError
)
from app.infrastructure.http_client.circuit_breaker.circuit_breaker import (
    CircuitBreaker
)
from app.infrastructure.http_client.constants.http_method import HttpMethod
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface
from app.infrastructure.http_client.http_client_configuration import HttpClientConfiguration

logger = logging.getLogger(__name__)


class HttpClient(HttpClientInterface):
    def __init__(self,
                 http_client_configuration: HttpClientConfiguration) -> None:
        self._http_client_configuration = http_client_configuration

        self._circuit_breaker: Optional[CircuitBreaker] = None
        if self._http_client_configuration.enable_circuit_breaker:
            self._circuit_breaker = CircuitBreaker.create()

        self._client: Optional[httpx.AsyncClient] = None
        self._lock: Lock = Lock()

        logger.info("HttpClient initialized successfully")

    @classmethod
    def create(cls,
               timeout: Optional[float] = None,
               max_keepalive_connections: Optional[int] = None,
               max_connections: Optional[int] = None,
               verify_ssl: Optional[bool] = None,
               follow_redirects: Optional[bool] = None,
               enable_circuit_breaker: Optional[bool] = None,
               retry_max_attempts: Optional[int] = None,
               retry_base_delay: Optional[float] = None,
               retry_max_delay: Optional[float] = None,
               retry_exponential_base: Optional[float] = None,
               retry_on_status_codes: Optional[Set[int]] = None) -> "HttpClient":
        config_kwargs = {}

        if timeout is not None:
            config_kwargs['timeout'] = timeout
        if max_keepalive_connections is not None:
            config_kwargs['max_keepalive_connections'] = max_keepalive_connections
        if max_connections is not None:
            config_kwargs['max_connections'] = max_connections
        if verify_ssl is not None:
            config_kwargs['verify_ssl'] = verify_ssl
        if follow_redirects is not None:
            config_kwargs['follow_redirects'] = follow_redirects
        if enable_circuit_breaker is not None:
            config_kwargs['enable_circuit_breaker'] = enable_circuit_breaker
        if retry_max_attempts is not None:
            config_kwargs['retry_max_attempts'] = retry_max_attempts
        if retry_base_delay is not None:
            config_kwargs['retry_base_delay'] = retry_base_delay
        if retry_max_delay is not None:
            config_kwargs['retry_max_delay'] = retry_max_delay
        if retry_exponential_base is not None:
            config_kwargs['retry_exponential_base'] = retry_exponential_base
        if retry_on_status_codes is not None:
            config_kwargs['retry_on_status_codes'] = retry_on_status_codes

        http_client_configuration = HttpClientConfiguration(**config_kwargs)

        return cls(
            http_client_configuration=http_client_configuration
        )

    async def start(self) -> None:
        async with self._lock:
            if self._client is not None:
                logger.debug("HttpClient already started")
                return

            logger.info("Starting HttpClient connection pool")

            try:
                limits = httpx.Limits(
                    max_keepalive_connections=self._http_client_configuration.max_keepalive_connections,
                    max_connections=self._http_client_configuration.max_connections
                )

                self._client = httpx.AsyncClient(
                    timeout=self._http_client_configuration.timeout,
                    follow_redirects=self._http_client_configuration.follow_redirects,
                    limits=limits,
                    verify=self._http_client_configuration.verify_ssl
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

        for attempt in range(self._http_client_configuration.retry_max_attempts):
            try:
                return await self._request(method, url, **kwargs)

            except Exception as e:
                last_error = e

                if not self._http_client_configuration.should_retry(e, attempt):
                    logger.debug("Not retrying request after failed attempt")
                    raise

                if attempt < self._http_client_configuration.retry_max_attempts - 1:
                    delay = self._http_client_configuration.calculate_delay(attempt)
                    logger.info("Retrying HTTP request after delay")
                    await asyncio.sleep(delay)

        logger.error("All retry attempts exhausted")
        if last_error:
            raise last_error
        raise HttpClientError("All retry attempts failed")

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

        logger.debug("Initiating HTTP request")

        try:
            response = await client.request(method.value, url, **kwargs)

            logger.debug("HTTP response received")

            if response.is_error:
                self._handle_error_response(response, url, method)

            return self._parse_response(response, url, method)

        except ExternalServiceError:
            raise
        except httpx.TimeoutException as e:
            logger.error("HTTP request timeout")
            raise NetworkError(f"Request timeout after {self._http_client_configuration.timeout}s") from e
        except httpx.RequestError as e:
            logger.error("Network error during HTTP request")
            raise NetworkError(f"Network error: {type(e).__name__}") from e
        except Exception as e:
            logger.exception("Unexpected error in HTTP request")
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
        if response.status_code == 204 or not response.content:
            logger.debug(
                "Empty or 204 response",
                extra={"url": url, "method": method.value}
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
            extra={"url": url, "method": method.value, "content_type": content_type}
        )
        return response.text

    @staticmethod
    def _looks_like_json(text: str) -> bool:
        if not text:
            return False
        stripped = text.strip()
        return (stripped.startswith("{") and stripped.endswith("}")) or \
            (stripped.startswith("[") and stripped.endswith("]"))
