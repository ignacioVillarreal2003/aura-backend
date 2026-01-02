import logging
from typing import Optional
from asyncio import Lock

from app.infrastructure.http_client.http_client import HttpClient
from app.infrastructure.http_client.http_client_configuration import HttpClientConfiguration
from app.infrastructure.http_client.retry_configuration import RetryConfiguration
from app.infrastructure.http_client.circuit_breaker_configuration import CircuitBreakerConfiguration

logger = logging.getLogger(__name__)

_global_http_client: Optional[HttpClient] = None
_global_http_client_lock: Lock = Lock()


async def get_global_http_client(*,
                                 configuration: Optional[HttpClientConfiguration] = None,
                                 timeout: float = 10.0,
                                 max_keepalive_connections: int = 5,
                                 max_connections: int = 10,
                                 verify_ssl: bool = True,
                                 follow_redirects: bool = True,
                                 auto_start: bool = True,
                                 enable_circuit_breaker: bool = True,
                                 retry_configuration: Optional[RetryConfiguration] = None,
                                 circuit_breaker_configuration: Optional[
                                     CircuitBreakerConfiguration] = None) -> HttpClient:
    global _global_http_client

    async with _global_http_client_lock:
        if _global_http_client is None:
            logger.info("Creating global HttpClient singleton")

            if configuration is None:
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

            _global_http_client = HttpClient(configuration=configuration)

            if auto_start:
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
