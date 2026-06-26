from fastapi import APIRouter, Depends

from app.api.controllers.processing.graph_extraction_controller.graph_extraction_controller_interface import (
    GraphExtractionControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_graph_extraction_service
from app.application.services.processing.graph_extraction_service.interfaces.graph_extraction_service_interface import (
    GraphExtractionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_request import (
    ExtractEntitiesRelationsRequest,
)
from app.domain.dtos.processing.graph_extraction.extract_entities_relations_response import (
    ExtractEntitiesRelationsResponse,
)
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class GraphExtractionController(GraphExtractionControllerInterface):
    async def extract_entities_relations(
            self,
            extract_entities_relations_request: ExtractEntitiesRelationsRequest,
            graph_extraction_service: GraphExtractionServiceInterface = Depends(get_graph_extraction_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> ExtractEntitiesRelationsResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_GRAPH_EXTRACTION}),
        )

        return await graph_extraction_service.extract_entities_relations(
            extract_entities_relations_request=extract_entities_relations_request,
            authenticated_user=authenticated_user,
        )


router = APIRouter()
graph_extraction_controller = GraphExtractionController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Entidades y relaciones extraídas del fragmento",
        "model": ExtractEntitiesRelationsResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    graph_extraction_controller.extract_entities_relations,
    methods=["POST"],
    response_model=ExtractEntitiesRelationsResponse,
    operation_id="extractEntitiesRelations",
    summary="Extraer entidades y relaciones",
    description=(
        "Extrae entidades y relaciones de un fragmento de texto para alimentar "
        "el grafo de conocimiento."
    ),
    responses=_response,
)
