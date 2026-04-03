from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Optional

from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_settings import RabbitMQManagerSettings


class RabbitMQManagerInterface(ABC):
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

    @property
    @abstractmethod
    def is_started(
            self
    ) -> bool:
        pass

    @property
    @abstractmethod
    def settings(
            self
    ) -> RabbitMQManagerSettings:
        pass

    @abstractmethod
    async def publish(
            self,
            routing_key: str,
            body: bytes,
            exchange_name: Optional[str] = None,
            persistent: bool = True,
            headers: Optional[dict[str, Any]] = None
    ) -> None:
        pass

    @abstractmethod
    async def start_consumer(
            self,
            queue_name: str,
            callback: Callable[..., Awaitable[None]],
            prefetch_count: Optional[int] = None
    ) -> None:
        pass

    @abstractmethod
    async def health_check(
            self
    ) -> dict[str, Any]:
        pass
