import logging
from fastapi import APIRouter, Depends

from app.api.controllers.support.document_classify_controller.interfaces.document_classify_controller_interface import (
    DocumentClassifyControllerInterface
)
from app.application.services.support.document_classify_service.document_classify_service import get_document_classify_service
from app.application.services.support.document_classify_service.interfaces.document_classify_service_interface import (
    DocumentClassifyServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.support.document_classify.classify_document_request import ClassifyDocumentRequest
from app.domain.dtos.support.document_classify.classify_document_response import ClassifyDocumentResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class DocumentClassifyController(DocumentClassifyControllerInterface):
    async def classify_document(
            self,
            classify_document_request: ClassifyDocumentRequest,
            document_classify_service: DocumentClassifyServiceInterface = Depends(get_document_classify_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user),
    ) -> ClassifyDocumentResponse:
        classify_document_response = await document_classify_service.classify_document(
            classify_document_request=classify_document_request,
            authenticated_user=authenticated_user,
        )

        return classify_document_response


router = APIRouter()
document_classify_controller = DocumentClassifyController()

router.post(
    "",
    response_model=ClassifyDocumentResponse,
)(document_classify_controller.classify_document)
