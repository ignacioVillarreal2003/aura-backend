from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.controllers.graph.graph_context_controller.interfaces.graph_context_controller_interface import (
    GraphContextControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.graph.graph_context_service.interfaces.graph_context_service_interface import (
    GraphContextServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_context.graph_context_request import GraphContextRequest
from app.domain.dtos.graph.graph_context.graph_context_response import GraphContextResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.api.dependencies.services import (
    get_graph_context_service,
)


class GraphContextController(GraphContextControllerInterface):
    async def get_context(
            self,
            graph_context_request: GraphContextRequest,
            graph_context_service: GraphContextServiceInterface = Depends(get_graph_context_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> GraphContextResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GRAPH_QUERY}),
        )

        return await graph_context_service.get_context(
            request=graph_context_request,
            authenticated_user=authenticated_user,
            database_session=database_session,
        )


router = APIRouter()
graph_context_controller = GraphContextController()

_error = default_error_responses(
    include_400=True,
    include_403=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Contexto compacto del grafo de conocimiento listo para inyectar en un prompt RAG",
        "model": GraphContextResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    graph_context_controller.get_context,
    methods=["POST"],
    response_model=GraphContextResponse,
    operation_id="getKnowledgeGraphContext",
    summary="Obtener contexto del grafo para RAG",
    description=(
        "Matchea los términos/pregunta contra las entidades del grafo (prefix + fulltext), "
        "expande relaciones de 1 salto alrededor de las mejores coincidencias y devuelve "
        "hechos legibles con procedencia documental. No invoca al LLM: es determinístico "
        "y de baja latencia, pensado para complementar la recuperación vectorial del RAG."
    ),
    responses=_response,
)
