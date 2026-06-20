from abc import ABC, abstractmethod

from app.application.services.graph.graph_stats_service.interfaces.graph_stats_service_interface import (
    GraphStatsServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_stats.graph_stats_response import GraphStatsResponse


class GraphStatsControllerInterface(ABC):
    @abstractmethod
    async def get_stats_manage(
            self,
            graph_stats_service: GraphStatsServiceInterface,
            authenticated_user: AuthenticatedUser,
    ) -> GraphStatsResponse:
        pass
