from abc import ABC, abstractmethod


class ConsumerInterface(ABC):
    @abstractmethod
    async def start(self) -> None:
        pass
