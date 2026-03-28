import logging

from fastapi import APIRouter, Depends

from app.api.controllers.controller_logging import log_controller
from app.api.controllers.document_classify_controller.interfaces.document_classify_controller_interface import (
    DocumentClassifyControllerInterface,
)
from app.application.services.document_classify_service.document_classify_service import get_document_classify_service
from app.application.services.document_classify_service.interfaces.document_classify_service_interface import (
    DocumentClassifyServiceInterface,
)
from app.domain.dtos.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.document_classify.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.authentication_provider.service_authentication_provider import get_service_caller_user

logger = logging.getLogger(__name__)


class DocumentClassifyController(DocumentClassifyControllerInterface):
    async def classify_document(
            self,
            body: ClassifyDocumentRequest,
            document_classify_service: DocumentClassifyServiceInterface = Depends(get_document_classify_service),
            authenticated_user: AuthenticationResponse = Depends(get_service_caller_user),
    ) -> ClassifyDocumentResponse:
        log_controller(
            logger,
            operation="classify_document",
            phase="start",
            user_id=authenticated_user.id,
            document_name_length=len(body.document_name or ""),
            content_length=len(body.content or ""),
        )

        response = await document_classify_service.classify_document(
            request=body,
            authenticated_user=authenticated_user,
        )

        log_controller(
            logger,
            operation="classify_document",
            phase="success",
            user_id=authenticated_user.id,
            document_type=response.type.value,
        )

        return response


router = APIRouter()

document_classify_controller = DocumentClassifyController()

router.post(
    "",
    response_model=ClassifyDocumentResponse,
)(document_classify_controller.classify_document)
