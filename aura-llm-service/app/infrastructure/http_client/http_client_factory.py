import logging
from typing import Optional, Set
from asyncio import Lock

from app.infrastructure.http_client.http_client import HttpClient

logger = logging.getLogger(__name__)

_global_http_client: Optional[HttpClient] = None
_global_http_client_lock: Lock = Lock()


async def get_global_http_client(
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
        retry_on_status_codes: Optional[Set[int]] = None
) -> HttpClient:
    global _global_http_client

    async with _global_http_client_lock:
        if _global_http_client is None:
            logger.info("Creating global HttpClient singleton")

            _global_http_client = HttpClient.create(
                timeout=timeout,
                max_keepalive_connections=max_keepalive_connections,
                max_connections=max_connections,
                verify_ssl=verify_ssl,
                follow_redirects=follow_redirects,
                enable_circuit_breaker=enable_circuit_breaker,
                retry_max_attempts=retry_max_attempts,
                retry_base_delay=retry_base_delay,
                retry_max_delay=retry_max_delay,
                retry_exponential_base=retry_exponential_base,
                retry_on_status_codes=retry_on_status_codes
            )

            await _global_http_client.start()
            logger.info("Global HttpClient started successfully")

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
            logger.info("Global HttpClient shut down successfully")
        else:
            logger.debug("Global HttpClient already shut down")
