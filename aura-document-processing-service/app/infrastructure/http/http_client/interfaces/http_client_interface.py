from abc import ABC, abstractmethod
from typing import Any, Optional, Union
import httpx


class HttpClientInterface(ABC):
    @abstractmethod
    async def start(
            self
    ) -> None:
        pass

    @abstractmethod
    async def stop(
            self
    ) -> None:
        pass

    @abstractmethod
    async def request(
            self,
            method: str,
            url: str,
            params: Optional[dict[str, Any]] = None,
            json: Optional[dict[str, Any]] = None,
            data: Optional[Union[dict[str, Any], bytes]] = None,
            headers: Optional[dict[str, str]] = None,
            timeout: Optional[float] = None,
            **kwargs
    ) -> httpx.Response:
        pass

    @abstractmethod
    async def get(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        pass

    @abstractmethod
    async def post(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        pass

    @abstractmethod
    async def put(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        pass

    @abstractmethod
    async def patch(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        pass

    @abstractmethod
    async def delete(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        pass

    @abstractmethod
    async def health_check(
            self
    ) -> dict[str, Any]:
        pass

    @property
    @abstractmethod
    def is_started(
            self
    ) -> bool:
        pass
