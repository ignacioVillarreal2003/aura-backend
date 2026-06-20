from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.controllers.graph.graph_path_controller.interfaces.graph_path_controller_interface import (
    GraphPathControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.graph.graph_path_service.interfaces.graph_path_service_interface import (
    GraphPathServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_path.find_path_request import FindPathRequest
from app.domain.dtos.graph.graph_path.graph_path_response import FindPathResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import (
    get_graph_path_service,
)

class GraphPathController(GraphPathControllerInterface):
    async def find_paths(
            self,
            find_path_request: FindPathRequest,
            graph_path_service: GraphPathServiceInterface = Depends(get_graph_path_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> FindPathResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GRAPH_PATH}),
        )

        return await graph_path_service.find_paths(
            request=find_path_request,
            authenticated_user=authenticated_user,
            database_session=database_session,
        )

router = APIRouter()
graph_path_controller = GraphPathController()

_error = default_error_responses(
    include_400=True,
    include_403=True,
    include_404=False,
    include_503=True,
)
_response = {
    200: {
        "description": "Caminos encontrados entre entidades",
        "model": FindPathResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    graph_path_controller.find_paths,
    methods=["POST"],
    response_model=FindPathResponse,
    operation_id="findKnowledgeGraphPaths",
    summary="Encontrar caminos entre entidades",
    description=(
        "Busca caminos (todos o el más corto) entre dos entidades en el grafo "
        "limitando por número máximo de saltos y aplicando filtrado por documentos accesibles."
    ),
    responses=_response,
)
