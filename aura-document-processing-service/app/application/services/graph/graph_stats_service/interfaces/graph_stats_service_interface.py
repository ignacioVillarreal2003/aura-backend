from abc import ABC, abstractmethod

from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_stats.graph_stats_response import GraphStatsResponse


class GraphStatsServiceInterface(ABC):
    @abstractmethod
    async def get_stats(
            self,
            *,
            authenticated_user: AuthenticatedUser,
    ) -> GraphStatsResponse:
        pass
