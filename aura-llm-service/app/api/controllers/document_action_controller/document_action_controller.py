from fastapi import APIRouter, Depends

from app.api.dependencies.idempotency import optional_idempotency_key
from app.api.dependencies.rate_limiter import strict_rate_limit
from app.api.controllers.document_action_controller.document_action_controller_interface import (
    DocumentActionControllerInterface
)
from app.api.openapi.common import default_error_responses
from app.application.services.document_action_service.document_action_service import get_document_action_service
from app.application.services.document_action_service.interfaces.document_action_service_interface import (
    DocumentActionServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.document_action.document_action_response import DocumentActionResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class DocumentActionController(DocumentActionControllerInterface):
    async def execute_document_action(
            self,
            document_action_request: DocumentActionRequest,
            document_action_service: DocumentActionServiceInterface = Depends(get_document_action_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(strict_rate_limit),
    ) -> DocumentActionResponse:
        return await document_action_service.execute_document_action(
            document_action_request=document_action_request,
            authenticated_user=authenticated_user
        )


router = APIRouter()
document_action_controller = DocumentActionController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Acción ejecutada",
        "model": DocumentActionResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    document_action_controller.execute_document_action,
    methods=["POST"],
    response_model=DocumentActionResponse,
    operation_id="executeDocumentAction",
    summary="Ejecutar acción sobre documento",
    description="Ejecuta una acción estructurada sobre los fragmentos del documento usando el LLM.",
    responses=_response,
)
