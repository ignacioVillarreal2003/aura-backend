from abc import ABC, abstractmethod

from app.domain.dtos.graph.graph_stats.graph_stats_response import GraphStatsResponse


class GraphStatsControllerInterface(ABC):
    @abstractmethod
    async def get_stats(self) -> GraphStatsResponse:
        pass
