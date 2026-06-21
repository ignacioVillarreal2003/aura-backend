from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.controllers.graph.graph_query_controller.interfaces.graph_query_controller_interface import (
    GraphQueryControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.graph.graph_query_service.interfaces.graph_query_service_interface import (
    GraphQueryServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_query.graph_query_request import GraphQueryRequest
from app.domain.dtos.graph.graph_query.graph_query_response import GraphQueryResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import (
    get_graph_query_service,
)


class GraphQueryController(GraphQueryControllerInterface):
    async def query(
            self,
            graph_query_request: GraphQueryRequest,
            graph_query_service: GraphQueryServiceInterface = Depends(get_graph_query_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> GraphQueryResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GRAPH_QUERY}),
        )

        return await graph_query_service.execute(
            request=graph_query_request,
            authenticated_user=authenticated_user,
            database_session=database_session,
        )


router = APIRouter()
graph_query_controller = GraphQueryController()

_error = default_error_responses(
    include_400=True,
    include_403=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Resultados estructurados desde el grafo de conocimiento",
        "model": GraphQueryResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    graph_query_controller.query,
    methods=["POST"],
    response_model=GraphQueryResponse,
    operation_id="queryKnowledgeGraph",
    summary="Consultar el grafo de conocimiento",
    description=(
        "Traduce una pregunta en lenguaje natural a una intención estructurada "
        "vía LLM y la ejecuta como Cypher parametrizado en Neo4j."
    ),
    responses=_response,
)
