from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Union
import httpx


class HttpClientInterface(ABC):
    @abstractmethod
    async def start_session(
            self
    ) -> None:
        pass

    @abstractmethod
    async def close_session(
            self
    ) -> None:
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
    async def delete(
            self,
            url: str,
            **kwargs
    ) -> httpx.Response:
        pass

    @abstractmethod
    def reset_metrics(
            self
    ) -> None:
        pass

    @abstractmethod
    def get_metrics(
            self
    ) -> Dict[str, int]:
        pass

    @property
    @abstractmethod
    def is_session_active(
            self
    ) -> bool:
        pass

    @property
    @abstractmethod
    def circuit_breaker_state(
            self
    ) -> str:
        pass
