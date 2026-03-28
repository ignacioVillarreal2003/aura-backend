from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
import httpx


class HttpClientInterface(ABC):
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def get(self, url: str, **kwargs) -> httpx.Response:
        pass

    @abstractmethod
    async def post(self, url: str, **kwargs) -> httpx.Response:
        pass

    @abstractmethod
    async def put(self, url: str, **kwargs) -> httpx.Response:
        pass

    @abstractmethod
    async def patch(self, url: str, **kwargs) -> httpx.Response:
        pass

    @abstractmethod
    async def delete(self, url: str, **kwargs) -> httpx.Response:
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        pass

    @property
    @abstractmethod
    def is_started(self) -> bool:
        pass

    @property
    @abstractmethod
    def client(self) -> httpx.AsyncClient:
        pass
