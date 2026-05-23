from abc import ABC, abstractmethod


class RerankerInterface(ABC):
    @abstractmethod
    async def rerank(
            self,
            query: str,
            candidates: list[str],
            top_n: int,
    ) -> list[int]:
        """Score each candidate against the query and return the indices of the
        top_n most relevant candidates sorted by descending score."""
        pass
