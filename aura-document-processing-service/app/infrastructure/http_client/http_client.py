import httpx
import logging
from typing import Optional, Dict, Any, Union, ClassVar
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
from aiobreaker import CircuitBreaker, CircuitBreakerError
from datetime import datetime, timedelta
from threading import Lock

from app.infrastructure.http_client.exceptions.http_client_exceptions import (
    HttpClientException,
    HttpClientConnectionException,
    HttpClientCircuitBreakerException,
    HttpClientTimeoutException
)
from app.infrastructure.http_client.interfaces.http_client_interface import HttpClientInterface

logger = logging.getLogger(__name__)


class HttpClient(HttpClientInterface):
    _instance: ClassVar[Optional['HttpClient']] = None
    _lock: ClassVar[Lock] = Lock()

    def __new__(
            cls,
            *args,
            **kwargs
    ):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
            self,
            timeout: float = 10.0,
            max_retries: int = 3,
            retry_min_wait: float = 2.0,
            retry_max_wait: float = 8.0,
            circuit_breaker_failures: int = 5,
            circuit_breaker_timeout: int = 60,
            max_connections: int = 100,
            max_keepalive_connections: int = 20,
            headers: Optional[Dict[str, str]] = None,
            verify_ssl: bool = True,
    ):
        if self._initialized:
            logger.debug("HttpClient already initialized")
            return

        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self.verify_ssl = verify_ssl

        self.default_headers = {
            "User-Agent": "HttpClient/1.0",
            **(headers or {})
        }

        self.breaker = CircuitBreaker(
            fail_max=circuit_breaker_failures,
            timeout_duration=timedelta(seconds=circuit_breaker_timeout),
            name="HttpClient"
        )

        self.limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections
        )

        self._client: Optional[httpx.AsyncClient] = None
        self._session_active = False

        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "circuit_breaker_opens": 0,
            "retries": 0,
        }

        self._initialized = True

        logger.info(
            f"HttpClient singleton initialized - "
            f"timeout={timeout}s, max_retries={max_retries}, "
            f"max_connections={max_connections}"
        )

    @classmethod
    def get_instance(
            cls
    ) -> 'HttpClient':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(
            cls
    ):
        with cls._lock:
            if cls._instance is not None:
                if cls._instance._session_active and cls._instance._client:
                    logger.warning(
                        "Resetting instance with active session. "
                        "Call close_session() first in async context."
                    )
                cls._instance = None
                logger.info("HttpClient singleton instance reset")

    async def __aenter__(
            self
    ):
        await self.start_session()
        return self

    async def __aexit__(
            self,
            exc_type,
            exc_val,
            exc_tb
    ):
        await self.close_session()

    async def start_session(
            self
    ):
        if self._session_active:
            logger.debug("Session already active")
            return

        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            limits=self.limits,
            headers=self.default_headers,
            verify=self.verify_ssl,
            follow_redirects=True,
        )
        self._session_active = True
        logger.info("HTTP session started")

    async def close_session(
            self
    ):
        if self._client and self._session_active:
            await self._client.aclose()
            self._session_active = False
            logger.info("HTTP session closed")
            logger.info(f"Final session metrics: {self.metrics}")

    def _create_retry_decorator(self):
        return retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(
                min=self.retry_min_wait,
                max=self.retry_max_wait
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
            client: httpx.AsyncClient,
            method: str,
            url: str,
            **kwargs
    ) -> httpx.Response:
        retry_decorator = self._create_retry_decorator()

        @retry_decorator
        async def _request():
            start_time = datetime.now()

            try:
                logger.debug(f"HTTP request: {method} {url}")
                resp = await client.request(method, url, **kwargs)
                resp.raise_for_status()

                duration = (datetime.now() - start_time).total_seconds()
                logger.debug(
                    f"HTTP response: {method} {url} - "
                    f"Status: {resp.status_code}, Duration: {duration:.3f}s"
                )

                return resp

            except httpx.TimeoutException as e:
                self.metrics["retries"] += 1
                logger.warning(f"Timeout on {method} {url}: {e}")
                raise HttpClientTimeoutException(f"Request timeout: {e}") from e

            except (
                    httpx.ConnectError,
                    httpx.NetworkError
            ) as e:
                self.metrics["retries"] += 1
                logger.warning(f"Connection error on {method} {url}: {e}")
                raise HttpClientConnectionException(f"Connection failed: {e}") from e

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"HTTP error on {method} {url}: "
                    f"Status {e.response.status_code}"
                )
                raise HttpClientException(
                    f"HTTP {e.response.status_code}: {e.response.text}"
                ) from e

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
        self.metrics["total_requests"] += 1

        request_headers = {**self.default_headers, **(headers or {})}

        if timeout:
            kwargs["timeout"] = httpx.Timeout(timeout)

        if self._session_active and self._client:
            client = self._client
            close_client = False
            logger.debug("Using persistent client (connection pool)")
        else:
            logger.debug("Creating temporary client (no session active)")
            client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout or self.timeout),
                limits=self.limits,
                headers=request_headers,
                verify=self.verify_ssl,
                follow_redirects=True,
            )
            close_client = True

        try:
            response = await self.breaker.call(
                self._safe_request,
                client,
                method,
                url,
                params=params,
                json=json,
                data=data,
                headers=request_headers if not self._session_active else headers,
                **kwargs
            )

            self.metrics["successful_requests"] += 1
            return response

        except CircuitBreakerError as e:
            self.metrics["circuit_breaker_opens"] += 1
            logger.error(f"Circuit breaker is open for {method} {url}")
            raise HttpClientCircuitBreakerException(
                "Service temporarily unavailable (circuit breaker open)"
            ) from e

        except Exception as e:
            self.metrics["failed_requests"] += 1
            logger.error(f"Request failed ({method} {url}): {e}")
            raise

        finally:
            if close_client:
                await client.aclose()

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

    def reset_metrics(
            self
    ):
        self.metrics = {key: 0 for key in self.metrics}
        logger.info("Metrics reset")

    def get_metrics(
            self
    ) -> Dict[str, int]:
        return self.metrics.copy()

    @property
    def is_session_active(
            self
    ) -> bool:
        return self._session_active

    @property
    def circuit_breaker_state(
            self
    ) -> str:
        return self.breaker.current_state
