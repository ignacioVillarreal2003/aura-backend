import logging

from fastapi import APIRouter, Depends

from app.api.dependencies.idempotency import optional_idempotency_key
from app.api.dependencies.rate_limiter import default_rate_limit
from app.api.controllers.document_classify.document_classify_controller_interface import (
    DocumentClassifyControllerInterface
)
from app.api.openapi.common import default_error_responses
from app.application.services.support.document_classify_service.document_classify_service import get_document_classify_service
from app.application.services.support.document_classify_service.interfaces.document_classify_service_interface import (
    DocumentClassifyServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.document_classify.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class DocumentClassifyController(DocumentClassifyControllerInterface):
    async def classify_document(
            self,
            classify_document_request: ClassifyDocumentRequest,
            document_classify_service: DocumentClassifyServiceInterface = Depends(get_document_classify_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
            _idemp: None = Depends(optional_idempotency_key),
            _rl: None = Depends(default_rate_limit),
    ) -> ClassifyDocumentResponse:
        logger.info(
            "Handling classify document request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        classify_document_response = await document_classify_service.classify_document(
            classify_document_request=classify_document_request,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Classify document completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return classify_document_response


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
