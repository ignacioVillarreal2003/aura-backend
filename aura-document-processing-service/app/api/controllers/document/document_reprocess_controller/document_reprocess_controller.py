import logging
from fastapi import APIRouter, Depends

from app.api.controllers.document.document_reprocess_controller.document_reprocess_controller_interface import (
    DocumentReprocessControllerInterface,
)
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.reprocess.reprocess_request import ReprocessRequest
from app.domain.dtos.document.reprocess.reprocess_response import ReprocessResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.messaging.rabbitmq.publisher.document_reprocess_publisher import (
    get_document_reprocess_publisher,
)
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.document_reprocess_publisher_interface import (
    DocumentReprocessPublisherInterface,
)

logger = logging.getLogger(__name__)


class DocumentReprocessController(DocumentReprocessControllerInterface):
    async def reprocess(
            self,
            request: ReprocessRequest,
            document_reprocess_publisher: DocumentReprocessPublisherInterface = Depends(
                get_document_reprocess_publisher
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> ReprocessResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.REPROCESS_DOCUMENT}),
        )
        message_id = await document_reprocess_publisher.publish(
            document_id=request.document_id,
            user=authenticated_user,
            prefer_docling=request.prefer_docling,
            post_process=request.post_process,
            post_process_graph=request.post_process_graph,
        )
        return ReprocessResponse(
            document_id=request.document_id,
            message_id=message_id,
            queued=True,
        )


router = APIRouter()
document_reprocess_controller = DocumentReprocessController()

_error_reprocess = default_error_responses(
    include_400=True,
    include_403=True,
    include_503=True,
)
_response_reprocess = {
    202: {
        "description": "Comando de reprocesamiento encolado exitosamente",
        "model": ReprocessResponse,
    },
    **_error_reprocess,
}

router.add_api_route(
    "",
    document_reprocess_controller.reprocess,
    methods=["POST"],
    response_model=ReprocessResponse,
    status_code=202,
    operation_id="reprocessDocument",
    summary="Reprocesar un documento desde su objeto almacenado",
    description=(
        "Encola un comando de reprocesamiento para el documento indicado. Re-ejecuta el "
        "pipeline completo de ingesta (re-descarga, re-chunk, re-embed) sobre el objeto ya "
        "almacenado: los fragmentos existentes se soft-borran y se reemplazan."
    ),
    responses=_response_reprocess,  # type: ignore[arg-type]
)
