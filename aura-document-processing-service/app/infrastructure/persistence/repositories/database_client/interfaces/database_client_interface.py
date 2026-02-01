from abc import ABC, abstractmethod
from typing import Generator
from sqlalchemy.orm import Session


class DatabaseClientInterface(ABC):
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
    def get_session(
            self
    ) -> Generator[Session, None, None]:
        pass

    @abstractmethod
    async def health_check(
            self
    ) -> bool:
        pass

    @property
    @abstractmethod
    def is_started(
            self
    ) -> bool:
        pass
