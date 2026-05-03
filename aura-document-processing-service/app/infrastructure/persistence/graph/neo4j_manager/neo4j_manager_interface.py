from abc import ABC, abstractmethod
from typing import Any, Optional
from neo4j import AsyncDriver


class Neo4jManagerInterface(ABC):
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def dispose(self) -> None:
        pass

    @property
    @abstractmethod
    def is_started(self) -> bool:
        pass

    @property
    @abstractmethod
    def driver(self) -> AsyncDriver:
        pass

    @property
    @abstractmethod
    def database(self) -> str:
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        pass

    @abstractmethod
    async def execute_read(
            self,
            cypher: str,
            parameters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        pass

    @abstractmethod
    async def execute_write(
            self,
            cypher: str,
            parameters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        pass
