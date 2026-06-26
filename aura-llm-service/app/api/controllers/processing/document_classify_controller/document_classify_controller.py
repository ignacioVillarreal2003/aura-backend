from fastapi import APIRouter, Depends

from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.controllers.processing.document_classify_controller.document_classify_controller_interface import (
    DocumentClassifyControllerInterface
)
from app.api.openapi.common import default_error_responses
from app.application.authorization.authorizer import Authorizer
from app.application.authorization.permissions import Permissions
from app.api.dependencies.app_state_services import get_document_classify_service
from app.application.services.processing.document_classify_service.interfaces.document_classify_service_interface import (
    DocumentClassifyServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.processing.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.processing.document_classify.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user


class DocumentClassifyController(DocumentClassifyControllerInterface):
    async def classify_document(
            self,
            classify_document_request: ClassifyDocumentRequest,
            document_classify_service: DocumentClassifyServiceInterface = Depends(get_document_classify_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _rl: None = Depends(default_rate_limit),
    ) -> ClassifyDocumentResponse:
        Authorizer.require_permissions(
            authenticated_user=authenticated_user,
            required_permissions=frozenset({Permissions.LLM_DOCUMENT_CLASSIFY}),
        )

        return await document_classify_service.classify_document(
            classify_document_request=classify_document_request,
            authenticated_user=authenticated_user,
        )


router = APIRouter()
document_classify_controller = DocumentClassifyController()

_error = default_error_responses(
    include_400=True,
    include_502=True,
    include_503=True,
)
_response = {
    200: {
        "description": "Clasificación del documento",
        "model": ClassifyDocumentResponse,
    },
    **_error,
}

router.add_api_route(
    "",
    document_classify_controller.classify_document,
    methods=["POST"],
    response_model=ClassifyDocumentResponse,
    operation_id="classifyDocument",
    summary="Clasificar documento",
    description="Clasifica el tipo y categoría de un documento usando el LLM.",
    responses=_response,
)
