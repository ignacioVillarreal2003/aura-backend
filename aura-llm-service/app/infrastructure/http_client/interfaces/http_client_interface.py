from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class HttpClientInterface(ABC):
    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    @abstractmethod
    async def get(self,
                  url: str,
                  params: Optional[Dict[str, Any]] = None,
                  headers: Optional[Dict[str, str]] = None,
                  **kwargs: Any) -> Any:
        pass

    @abstractmethod
    async def post(self,
                   url: str,
                   json: Optional[Dict[str, Any]] = None,
                   data: Optional[Any] = None,
                   headers: Optional[Dict[str, str]] = None,
                   **kwargs: Any) -> Any:
        pass

    @abstractmethod
    async def put(self,
                  url: str,
                  json: Optional[Dict[str, Any]] = None,
                  data: Optional[Any] = None,
                  headers: Optional[Dict[str, str]] = None,
                  **kwargs: Any) -> Any:
        pass

    @abstractmethod
    async def delete(self,
                     url: str,
                     headers: Optional[Dict[str, str]] = None,
                     **kwargs: Any) -> Any:
        pass
