from fastapi import APIRouter, Depends, Request

from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.configuration.graph.knowledge_graph_settings import KnowledgeGraphSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_ontology.graph_ontology_response import GraphOntologyResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


def _get_knowledge_graph_settings(request: Request) -> KnowledgeGraphSettings:
    return getattr(request.app.state, "knowledge_graph_settings", KnowledgeGraphSettings())


class GraphOntologyController:
    async def get_ontology(
            self,
            kg_settings: KnowledgeGraphSettings = Depends(_get_knowledge_graph_settings),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> GraphOntologyResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GRAPH_ONTOLOGY}),
        )

        return GraphOntologyResponse(
            entity_types=kg_settings.resolve_allowed_entity_types(),
            relation_types=kg_settings.resolve_allowed_relation_types(),
            query_max_results=kg_settings.query_max_results,
            query_max_depth=kg_settings.query_max_neighbor_depth,
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
