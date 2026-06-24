from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.processors.rerankers.reranker_settings import RerankerSettings


class RerankerInterface(ABC):
    @abstractmethod
    def __init__(self, reranker_settings: "RerankerSettings") -> None:
        pass

    @abstractmethod
    async def rerank(
            self,
            query: str,
            candidates: list[str],
            top_n: int,
    ) -> list[int]:
        pass

    @abstractmethod
    async def rerank_with_scores(
            self,
            query: str,
            candidates: list[str],
            top_n: int,
    ) -> list[tuple[int, float]]:
        pass
