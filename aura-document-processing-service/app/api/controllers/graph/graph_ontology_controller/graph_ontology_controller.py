from fastapi import APIRouter, Depends

from app.api.controllers.graph.graph_ontology_controller.interfaces.graph_ontology_controller_interface import (
    GraphOntologyControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.application.services.graph.graph_ontology_service.interfaces.graph_ontology_service_interface import (
    GraphOntologyServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_ontology.graph_ontology_response import GraphOntologyResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.api.dependencies.services import (
    get_graph_ontology_service,
)

class GraphOntologyController(GraphOntologyControllerInterface):
    async def get_ontology(
            self,
            graph_ontology_service: GraphOntologyServiceInterface = Depends(get_graph_ontology_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> GraphOntologyResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GRAPH_ONTOLOGY}),
        )

        return await graph_ontology_service.get_ontology(
            authenticated_user=authenticated_user,
        )

router = APIRouter()
graph_ontology_controller = GraphOntologyController()

_error = default_error_responses(
    include_403=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Metadatos de la ontología activa del grafo de conocimiento",
        "model": GraphOntologyResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    graph_ontology_controller.get_ontology,
    methods=["GET"],
    response_model=GraphOntologyResponse,
    operation_id="getKnowledgeGraphOntology",
    summary="Obtener ontología del grafo",
    description=(
        "Devuelve los tipos de entidades y relaciones configurados para esta instancia del "
        "grafo de conocimiento, junto con los límites operacionales de la API (max_results, max_depth). "
        "Use este endpoint para poblar filtros dinámicos en el frontend sin hardcodear tipos."
    ),
    responses=_response,
)
