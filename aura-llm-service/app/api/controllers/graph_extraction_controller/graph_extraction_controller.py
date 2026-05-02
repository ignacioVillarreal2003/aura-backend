import logging

from fastapi import APIRouter, Depends

from app.api.controllers.graph_extraction_controller.graph_extraction_controller_interface import (
    GraphExtractionControllerInterface,
)
from app.api.dependencies.idempotency import optional_idempotency_key
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.services.graph_extraction_service.graph_extraction_service import (
    get_graph_extraction_service,
)
from app.application.services.graph_extraction_service.interfaces.graph_extraction_service_interface import (
    GraphExtractionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.extraction.extract_entities_relations_request import (
    ExtractEntitiesRelationsRequest,
)
from app.domain.dtos.graph.extraction.extract_entities_relations_response import (
    ExtractEntitiesRelationsResponse,
)
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class GraphExtractionController(GraphExtractionControllerInterface):
    async def extract_entities_relations(
            self,
            extract_entities_relations_request: ExtractEntitiesRelationsRequest,
            graph_extraction_service: GraphExtractionServiceInterface = Depends(get_graph_extraction_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(default_rate_limit),
    ) -> ExtractEntitiesRelationsResponse:
        logger.info(
            "Handling graph extraction request",
            extra={
                "user_id": authenticated_user.id,
                "document_id": extract_entities_relations_request.document_id,
                "fragment_id": extract_entities_relations_request.fragment_id,
            },
        )

        response = await graph_extraction_service.extract_entities_relations(
            extract_entities_relations_request=extract_entities_relations_request,
            authenticated_user=authenticated_user,
        )

        logger.info(
            "Graph extraction completed successfully",
            extra={
                "user_id": authenticated_user.id,
                "document_id": extract_entities_relations_request.document_id,
                "fragment_id": extract_entities_relations_request.fragment_id,
                "entities_count": len(response.entities),
                "relations_count": len(response.relations),
            },
        )

        return response


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
