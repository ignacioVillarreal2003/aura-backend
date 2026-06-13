from abc import ABC, abstractmethod
import redis.asyncio as aioredis


class RedisClientInterface(ABC):
    @property
    @abstractmethod
    def client(self) -> aioredis.Redis:
        pass

    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def dispose(self) -> None:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass
