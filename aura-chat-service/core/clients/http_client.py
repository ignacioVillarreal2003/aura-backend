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
                raise HttpClientException(
                    f"HTTP {response.status_code}",
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
