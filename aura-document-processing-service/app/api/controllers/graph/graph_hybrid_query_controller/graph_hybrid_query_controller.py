from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.controllers.graph.graph_hybrid_query_controller.graph_hybrid_query_controller_interface import (
    GraphHybridQueryControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.services.graph.hybrid_retrieval_orchestrator.hybrid_retrieval_orchestrator import (
    get_hybrid_retrieval_orchestrator,
)
from app.application.services.graph.hybrid_retrieval_orchestrator.interfaces.hybrid_retrieval_orchestrator_interface import (
    HybridRetrievalOrchestratorInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_query.graph_hybrid_query_response import (
    GraphHybridQueryResponse,
)
from app.domain.dtos.graph.graph_query.graph_query_request import GraphQueryRequest
from app.infrastructure.http.authentication_provider.authentication_provider import (
    get_authenticated_user,
)
from app.infrastructure.persistence.database.database_manager.database_manager import (
    get_database_session,
)


class GraphHybridQueryController(GraphHybridQueryControllerInterface):
    async def hybrid_query(
            self,
            graph_query_request: GraphQueryRequest,
            hybrid_retrieval_orchestrator: HybridRetrievalOrchestratorInterface = Depends(
                get_hybrid_retrieval_orchestrator
            ),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> GraphHybridQueryResponse:
        return await hybrid_retrieval_orchestrator.retrieve(
            request=graph_query_request,
            authenticated_user=authenticated_user,
            database_session=database_session,
        )


router = APIRouter()
graph_hybrid_query_controller = GraphHybridQueryController()

_error = default_error_responses(
    include_400=True,
    include_403=True,
    include_404=False,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Resultado híbrido (KG primero, fallback RAG)",
        "model": GraphHybridQueryResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    graph_hybrid_query_controller.hybrid_query,
    methods=["POST"],
    response_model=GraphHybridQueryResponse,
    operation_id="hybridKnowledgeGraphQuery",
    summary="Consulta híbrida KG + RAG",
    description=(
        "Intenta resolver la pregunta con el grafo de conocimiento y, si la "
        "intención no es confiable o no hay resultados, hace fallback al "
        "pipeline RAG vectorial existente sin modificarlo."
    ),
    responses=_response,
)
