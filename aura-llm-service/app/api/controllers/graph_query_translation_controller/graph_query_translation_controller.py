import logging

from fastapi import APIRouter, Depends

from app.api.controllers.graph_query_translation_controller.graph_query_translation_controller_interface import (
    GraphQueryTranslationControllerInterface,
)
from app.api.dependencies.idempotency import optional_idempotency_key
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.services.graph_query_translation_service.graph_query_translation_service import (
    get_graph_query_translation_service,
)
from app.application.services.graph_query_translation_service.interfaces.graph_query_translation_service_interface import (
    GraphQueryTranslationServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.graph.query_translation.translate_graph_query_request import (
    TranslateGraphQueryRequest,
)
from app.domain.dtos.graph.query_translation.translate_graph_query_response import (
    TranslateGraphQueryResponse,
)
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class GraphQueryTranslationController(GraphQueryTranslationControllerInterface):
    async def translate_graph_query(
            self,
            translate_graph_query_request: TranslateGraphQueryRequest,
            graph_query_translation_service: GraphQueryTranslationServiceInterface = Depends(
                get_graph_query_translation_service
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(default_rate_limit),
    ) -> TranslateGraphQueryResponse:
        logger.info(
            "Handling graph query translation request",
            extra={
                "user_id": authenticated_user.id,
                "question_len": len(translate_graph_query_request.question),
            },
        )

        response = await graph_query_translation_service.translate_graph_query(
            translate_graph_query_request=translate_graph_query_request,
            authenticated_user=authenticated_user,
        )

        logger.info(
            "Graph query translation completed successfully",
            extra={
                "user_id": authenticated_user.id,
                "intent": response.intent.value,
                "confidence": response.confidence,
            },
        )

        return response


router = APIRouter()
graph_query_translation_controller = GraphQueryTranslationController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Intención estructurada inferida a partir de la pregunta",
        "model": TranslateGraphQueryResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    graph_query_translation_controller.translate_graph_query,
    methods=["POST"],
    response_model=TranslateGraphQueryResponse,
    operation_id="translateGraphQuery",
    summary="Traducir pregunta a intención de grafo",
    description=(
        "Traduce una pregunta en lenguaje natural a un intent estructurado y "
        "parámetros validados sobre la ontología del grafo. Nunca devuelve Cypher."
    ),
    responses=_response,
)
