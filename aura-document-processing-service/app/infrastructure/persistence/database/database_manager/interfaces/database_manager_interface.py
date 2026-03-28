from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database.database_manager.database_manager_settings import (
    DatabaseManagerSettings
)


class DatabaseManagerInterface(ABC):
    @property
    @abstractmethod
    def settings(self) -> DatabaseManagerSettings:
        pass

    @property
    @abstractmethod
    def is_initialized(self) -> bool:
        pass

    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def dispose(self) -> None:
        pass

    @abstractmethod
    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        pass
