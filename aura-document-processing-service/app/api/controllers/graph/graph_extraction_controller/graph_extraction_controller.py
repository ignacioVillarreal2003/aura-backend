import logging
from fastapi import APIRouter, Depends, Path

from app.api.controllers.graph.graph_extraction_controller.graph_extraction_controller_interface import (
    GraphExtractionControllerInterface,
)
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.services import get_graph_extraction_service
from app.application.services.graph.graph_extraction_service.interfaces.graph_extraction_service_interface import (
    GraphExtractionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.graph_extraction.graph_extraction_progress import (
    GraphExtractionProgressResponse,
)
from app.domain.dtos.graph.graph_extraction.graph_reextract_request import GraphReextractRequest
from app.domain.dtos.graph.graph_extraction.graph_reextract_response import GraphReextractResponse
from app.domain.field_limits import MAX_ID
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.messaging.rabbitmq.publisher.graph_extraction_publisher import (
    get_graph_extraction_publisher,
)
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.graph_extraction_publisher_interface import (
    GraphExtractionPublisherInterface,
)

logger = logging.getLogger(__name__)


class GraphExtractionController(GraphExtractionControllerInterface):
    async def get_extraction_progress(
            self,
            document_id: int = Path(..., ge=1, le=MAX_ID, description="ID del documento."),
            graph_extraction_service: GraphExtractionServiceInterface = Depends(
                get_graph_extraction_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> GraphExtractionProgressResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GRAPH_EXTRACTION_PROGRESS}),
        )

        return await graph_extraction_service.get_progress(document_id=document_id)

    async def reextract(
            self,
            request: GraphReextractRequest,
            graph_extraction_publisher: GraphExtractionPublisherInterface = Depends(
                get_graph_extraction_publisher
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> GraphReextractResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.GRAPH_REEXTRACT}),
        )
        message_id = await graph_extraction_publisher.publish(
            document_id=request.document_id,
            user=authenticated_user,
            force=request.force,
        )
        return GraphReextractResponse(
            document_id=request.document_id,
            message_id=message_id,
            force=request.force,
            queued=True,
        )


router = APIRouter()
graph_extraction_controller = GraphExtractionController()

_error_progress = default_error_responses(
    include_400=False,
    include_403=True,
    include_503=True,
)
_response_progress = {
    200: {
        "description": "Progreso del job de extracción del grafo de conocimiento",
        "model": GraphExtractionProgressResponse,
    },
    **_error_progress,
}

router.add_api_route(
    "/progress/{document_id}",
    graph_extraction_controller.get_extraction_progress,
    methods=["GET"],
    response_model=GraphExtractionProgressResponse,
    operation_id="getGraphExtractionProgress",
    summary="Consultar progreso de extracción del grafo",
    description=(
        "Devuelve el estado actual del job de extracción del grafo de conocimiento "
        "para un documento dado. Si no hay job activo, devuelve is_running=False."
    ),
    responses=_response_progress,
)

_error_reextract = default_error_responses(
    include_400=True,
    include_403=True,
    include_503=True,
)
_response_reextract = {
    200: {
        "description": "Comando de re-extracción encolado exitosamente",
        "model": GraphReextractResponse,
    },
    **_error_reextract,
}

router.add_api_route(
    "/reextract",
    graph_extraction_controller.reextract,
    methods=["POST"],
    response_model=GraphReextractResponse,
    operation_id="reextractKnowledgeGraph",
    summary="Disparar re-extracción del grafo de conocimiento",
    description=(
        "Encola un comando de extracción del grafo para el documento indicado. "
        "Con force=True libera cualquier lock activo antes de encolar. "
        "Las entidades y relaciones existentes se fusionan idempotentemente."
    ),
    responses=_response_reextract,
)
