import logging

from app.application.services.graph.graph_stats_service.interfaces.graph_stats_service_interface import (
    GraphStatsServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_stats.graph_stats_response import GraphStatsResponse
from app.infrastructure.persistence.graph.repositories.interfaces.graph_stats_repository_interface import (
    GraphStatsRepositoryInterface,
)

logger = logging.getLogger(__name__)


class GraphStatsService(GraphStatsServiceInterface):
    def __init__(
            self,
            *,
            stats_repository: GraphStatsRepositoryInterface,
    ) -> None:
        self._stats_repository = stats_repository

    async def get_stats(
            self,
            *,
            authenticated_user: AuthenticatedUser,
    ) -> GraphStatsResponse:
        return await self._stats_repository.get_stats()
