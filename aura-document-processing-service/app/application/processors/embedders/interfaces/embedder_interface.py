from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.processors.embedders.embedder_settings import EmbedderSettings


class EmbedderInterface(ABC):
    @abstractmethod
    def __init__(self, embedder_settings: "EmbedderSettings") -> None:
        pass

    @abstractmethod
    def embed_documents(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        pass

    @abstractmethod
    def embed_query(
            self,
            text: str
    ) -> list[float]:
        pass

    @abstractmethod
    async def aembed_documents(
            self,
            texts: list[str]
    ) -> list[list[float]]:
        pass

    @abstractmethod
    async def aembed_query(
            self,
            text: str
    ) -> list[float]:
        pass
