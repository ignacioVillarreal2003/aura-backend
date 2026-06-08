from fastapi import APIRouter, Depends

from app.api.controllers.graph.graph_stats_controller.graph_stats_controller_interface import (
    GraphStatsControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.services.graph.graph_stats_service.graph_stats_service import get_graph_stats_service
from app.application.services.graph.graph_stats_service.interfaces.graph_stats_service_interface import (
    GraphStatsServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_stats.graph_stats_response import GraphStatsResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class GraphStatsController(GraphStatsControllerInterface):
    async def get_stats(
            self,
            graph_stats_service: GraphStatsServiceInterface = Depends(get_graph_stats_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> GraphStatsResponse:
        return await graph_stats_service.get_stats(
            authenticated_user=authenticated_user,
        )


router = APIRouter()
graph_stats_controller = GraphStatsController()

_error = default_error_responses(
    include_403=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Estadísticas del grafo de conocimiento",
        "model": GraphStatsResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    graph_stats_controller.get_stats,
    methods=["GET"],
    response_model=GraphStatsResponse,
    operation_id="getKnowledgeGraphStats",
    summary="Estadísticas del grafo de conocimiento",
    description=(
        "Devuelve métricas de cobertura del grafo: total de entidades, relaciones, "
        "entidades por tipo y número de documentos indexados. Útil para dashboards de "
        "monitorización y para dar feedback al usuario sobre la cobertura del grafo."
    ),
    responses=_response,
)
