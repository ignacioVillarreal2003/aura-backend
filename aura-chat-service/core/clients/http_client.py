import logging

import httpx

from core.clients.exceptions import (
    HttpClientConnectionException,
    HttpClientException,
    HttpClientTimeoutException,
)

logger = logging.getLogger(__name__)


class AsyncHttpClient:
    def __init__(self, timeout: int = 30):
        self._timeout = timeout

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
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method, url, json=json, headers=headers
                )
            if response.status_code >= 400:
                await response.aread()
                snippet = response.text[:1000] if response.text else ""
                msg = f"HTTP {response.status_code}"
                if snippet.strip():
                    msg = f"{msg}: {snippet.strip()}"
                logger.warning(
                    "HTTP error response.",
                    extra={
                        "url": url,
                        "status_code": response.status_code,
                        "body_preview": snippet[:200],
                    },
                )
                raise HttpClientException(
                    msg,
                    status_code=response.status_code,
                )
            return response
        except httpx.TimeoutException as e:
            raise HttpClientTimeoutException() from e
        except httpx.ConnectError as e:
            raise HttpClientConnectionException() from e
        except HttpClientException:
            raise
        except Exception as e:
            raise HttpClientException(str(e)) from e
