from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseManagerInterface(ABC):
    @abstractmethod
    async def initialize(
            self
    ) -> None:
        pass

    @abstractmethod
    async def dispose(
            self
    ) -> None:
        pass

    @abstractmethod
    @asynccontextmanager
    async def session(
            self
    ) -> AsyncGenerator[AsyncSession, None]:
        pass

    @abstractmethod
    async def health_check(
            self
    ) -> Dict[str, Any]:
        pass

    @property
    @abstractmethod
    def is_initialized(
            self
    ) -> bool:
        pass
