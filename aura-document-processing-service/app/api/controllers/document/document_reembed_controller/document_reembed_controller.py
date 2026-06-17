import logging
from fastapi import APIRouter, Depends

from app.api.controllers.document.document_reembed_controller.document_reembed_controller_interface import (
    DocumentReembedControllerInterface,
)
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.reembed.reembed_request import ReembedRequest
from app.domain.dtos.document.reembed.reembed_response import ReembedResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.messaging.rabbitmq.publisher.document_reembed_publisher import (
    get_document_reembed_publisher,
)
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.document_reembed_publisher_interface import (
    DocumentReembedPublisherInterface,
)

logger = logging.getLogger(__name__)


class DocumentReembedController(DocumentReembedControllerInterface):
    async def reembed(
            self,
            request: ReembedRequest,
            document_reembed_publisher: DocumentReembedPublisherInterface = Depends(
                get_document_reembed_publisher
            ),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(strict_rate_limit),
    ) -> ReembedResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.REEMBED_DOCUMENT}),
        )
        message_id = await document_reembed_publisher.publish(
            document_id=request.document_id,
            user=authenticated_user,
            force=request.force,
        )
        return ReembedResponse(
            document_id=request.document_id,
            message_id=message_id,
            force=request.force,
            queued=True,
        )


router = APIRouter()
document_reembed_controller = DocumentReembedController()

_error_reembed = default_error_responses(
    include_400=True,
    include_403=True,
    include_503=True,
)
_response_reembed = {
    202: {
        "description": "Comando de re-embedding encolado exitosamente",
        "model": ReembedResponse,
    },
    **_error_reembed,
}

router.add_api_route(
    "",
    document_reembed_controller.reembed,
    methods=["POST"],
    response_model=ReembedResponse,
    status_code=202,
    operation_id="reembedDocument",
    summary="Re-embeber los fragmentos de un documento con el modelo activo",
    description=(
        "Encola un comando de re-embedding para el documento indicado. Re-genera los "
        "vectores de los fragmentos existentes con el modelo de embeddings activo "
        "(migración de modelo), preservando el texto de los chunks. Con force=False solo "
        "re-embebe los fragmentos cuyo modelo difiere del activo (idempotente)."
    ),
    responses=_response_reembed,  # type: ignore[arg-type]
)
