from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.processors.rerankers.reranker_settings import RerankerSettings


class RerankerInterface(ABC):
    @abstractmethod
    def __init__(self, reranker_settings: "RerankerSettings") -> None:
        ...

    @abstractmethod
    async def rerank(
            self,
            query: str,
            candidates: list[str],
            top_n: int,
    ) -> list[int]:
        """Score each candidate against the query and return the indices of the
        top_n most relevant candidates sorted by descending score."""
