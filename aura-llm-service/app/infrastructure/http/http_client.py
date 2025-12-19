import httpx
import logging
from typing import Optional, Any, Dict, Union
from threading import Lock
from contextlib import asynccontextmanager

from app.application.exceptions.http_client_exceptions import (
    HttpClientError,
    ClientNotInitializedError,
    ExternalServiceException,
    NetworkException,
)

logger = logging.getLogger(__name__)


class HttpClient:
    _instance: Optional['HttpClient'] = None
    _lock: Lock = Lock()

    def __new__(cls,
                *args,
                **kwargs) -> 'HttpClient':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    logger.debug("Creating HttpClient instance")
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self,
                 timeout: float = 10.0,
                 max_keepalive: int = 5,
                 max_connections: int = 10,
                 verify_ssl: bool = True) -> None:
        if hasattr(self, '_initialized') and self._initialized:
            logger.debug("HttpClient already initialized")
            return

        self._timeout: float = timeout
        self._max_keepalive: int = max_keepalive
        self._max_connections: int = max_connections
        self._verify_ssl: bool = verify_ssl

        self._client: Optional[httpx.AsyncClient] = None
        self._is_started: bool = False

        self._limits = httpx.Limits(
            max_keepalive_connections=max_keepalive,
            max_connections=max_connections
        )

        self._initialized = True
        logger.info("HttpClient configured")

    def start(self) -> None:
        if self._is_started and self._client:
            logger.debug("HttpClient is already running")
            return

        logger.info("Initializing HttpClient connection pool")

        try:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                limits=self._limits,
                verify=self._verify_ssl
            )
            self._is_started = True
            logger.info("HttpClient started successfully")

        except Exception as e:
            logger.critical(f"Failed to initialize HttpClient: {e}")
            self._client = None
            self._is_started = False
            raise HttpClientError(f"Failed to initialize HttpClient: {e}")

    async def stop(self) -> None:
        if not self._client:
            logger.debug("HTTPClient is not running")
            return

        logger.info("Closing HTTPClient connection pool")

        try:
            await self._client.aclose()
            logger.info("HTTPClient closed successfully")

        except Exception as e:
            logger.error(f"Error closing HTTPClient: {e}")

        finally:
            self._client = None
            self._is_started = False

    @asynccontextmanager
    async def _ensure_client(self):
        if not self._client or not self._is_started:
            logger.error("HTTPClient is not initialized.")
            raise ClientNotInitializedError("HTTPClient is not initialized.")

        yield self._client

    async def get(self,
                  url: str,
                  params: Optional[Dict[str, Any]] = None,
                  headers: Optional[Dict[str, str]] = None,
                  **kwargs) -> Any:
        return await self._request("GET", url, params=params, headers=headers, **kwargs)

    async def post(self,
                   url: str,
                   json: Optional[Dict[str, Any]] = None,
                   data: Optional[Any] = None,
                   headers: Optional[Dict[str, str]] = None) -> Any:
        return await self._request("POST", url, json=json, data=data, headers=headers, **kwargs)

    async def put(self,
                  url: str,
                  json: Optional[Dict[str, Any]] = None,
                  data: Optional[Any] = None,
                  headers: Optional[Dict[str, str]] = None,
                  **kwargs) -> Any:
        return await self._request("PUT", url, json=json, data=data, headers=headers, **kwargs)

    async def delete(self,
                     url: str,
                     headers: Optional[Dict[str, str]] = None,
                     **kwargs) -> Any:
        return await self._request("DELETE", url, headers=headers, **kwargs)

    async def _request(self,
                       method: str,
                       url: str,
                       **kwargs: Any) -> Any:
        async with self._ensure_client() as client:
            logger.debug(f"HTTP request: {method} {url}")

            try:
                response = await client.request(method, url, **kwargs)
                logger.debug(f"HTTP response: {response.status_code}")

                if response.is_error:
                    logger.warning(f"External service error: {response.status_code} {url}")
                    response.raise_for_status()

                if response.status_code == 204:
                    logger.debug("Response is 204, No Content")
                    return None

                try:
                    return response.json()

                except ValueError:
                    logger.warning(f"Response from {url} is not JSON")
                    return response.text

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP status error: {e.response.status_code}")
                raise ExternalServiceException(status_code=e.response.status_code,
                                               message=e.response.text,
                                               url=url)

            except httpx.TimeoutException:
                logger.error(f"Request timeout: {url}")
                raise NetworkException(f"Request timeout: {url}")

            except httpx.RequestError:
                logger.error(f"Network error: {url}")
                raise NetworkException(f"Network error: {url}")

            except Exception:
                logger.exception(f"Unexpected error in HTTPClient: {url}")
                raise NetworkException(f"Unexpected error in HTTPClient: {url}")


_global_http_client: Optional[HttpClient] = None
_global_http_client_lock: Lock = Lock()


def create_http_client(*,
                       timeout: float = 10.0,
                       max_keepalive: int = 5,
                       max_connections: int = 10,
                       verify_ssl: bool = True) -> HttpClient:
    return HttpClient(
        timeout=timeout,
        max_keepalive=max_keepalive,
        max_connections=max_connections,
        verify_ssl=verify_ssl
    )


def get_global_http_client(*,
                           timeout: float = 10.0,
                           max_keepalive: int = 5,
                           max_connections: int = 10,
                           verify_ssl: bool = True) -> HttpClient:
    global _global_http_client

    if _global_http_client is not None:
        logger.debug("Returning existing global HttpClient instance")
        return _global_http_client

    with _global_http_client_lock:
        if _global_http_client is not None:
            logger.debug("Global HttpClient created by concurrent thread")
            return _global_http_client

        logger.debug("Creating global HttpClient singleton")

        _global_http_client = create_http_client(
            timeout=timeout,
            max_keepalive=max_keepalive,
            max_connections=max_connections,
            verify_ssl=verify_ssl
        )

        logger.info("Global HttpClient singleton created")
        return _global_http_client
