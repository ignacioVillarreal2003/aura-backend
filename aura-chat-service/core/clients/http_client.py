import asyncio
import logging
import random

import httpx

from core.clients.exceptions import (
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException,
)

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class AsyncHttpClient:
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self._timeout = timeout
        self._max_retries = max_retries

    async def get(self, url: str, headers: dict | None = None) -> httpx.Response:
        return await self._request("GET", url, headers=headers)

    async def post(
        self,
        url: str,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        return await self._request("POST", url, json=json, headers=headers)

    async def _request(
        self,
        method: str,
        url: str,
        json: dict | None = None,
        headers: dict | None = None,
    ) -> httpx.Response:
        last_exc: BaseException | None = None

        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.request(
                        method, url, json=json, headers=headers
                    )

                if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries - 1:
                    delay = min(2.0, 0.1 * (2 ** attempt) + random.uniform(0, 0.05))
                    logger.warning(
                        "Retryable HTTP error, will retry.",
                        extra={
                            "url": url,
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                            "delay_seconds": round(delay, 3),
                        },
                    )
                    await asyncio.sleep(delay)
                    continue

                if response.status_code >= 400:
                    snippet = ""
                    try:
                        await response.aread()
                        snippet = response.text[:200] if response.text else ""
                    except Exception:
                        pass
                    logger.warning(
                        "HTTP error response.",
                        extra={
                            "url": url,
                            "status_code": response.status_code,
                            "body_preview": snippet,
                        },
                    )
                    raise HttpClientException(
                        f"HTTP {response.status_code}",
                        status_code=response.status_code,
                    )

                return response

            except httpx.TimeoutException as e:
                last_exc = e
                if attempt < self._max_retries - 1:
                    delay = min(2.0, 0.1 * (2 ** attempt) + random.uniform(0, 0.05))
                    logger.warning(
                        "Request timed out, will retry.",
                        extra={"url": url, "attempt": attempt + 1},
                    )
                    await asyncio.sleep(delay)
                    continue
                raise HttpClientTimeoutException() from e

            except httpx.ConnectError as e:
                last_exc = e
                if attempt < self._max_retries - 1:
                    delay = min(2.0, 0.1 * (2 ** attempt) + random.uniform(0, 0.05))
                    logger.warning(
                        "Connection failed, will retry.",
                        extra={"url": url, "attempt": attempt + 1},
                    )
                    await asyncio.sleep(delay)
                    continue
                raise HttpClientConnectionException() from e

            except HttpClientException:
                raise

            except Exception as e:
                raise HttpClientException(str(e)) from e

        raise HttpClientConnectionException() from last_exc
