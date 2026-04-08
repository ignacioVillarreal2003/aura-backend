from abc import ABC, abstractmethod


class EmbedderInterface(ABC):
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
