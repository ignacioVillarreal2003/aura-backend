import logging
from fastapi import APIRouter, Depends

from app.api.controllers.document.document_action_controller.interfaces.document_action_controller_interface import (
    DocumentActionControllerInterface
)
from app.application.services.document.document_action_service.document_action_service import get_document_action_service
from app.application.services.document.document_action_service.interfaces.document_action_service_interface import (
    DocumentActionServiceInterface
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.dtos.document.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.document.document_action.document_action_response import DocumentActionResponse
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user

logger = logging.getLogger(__name__)


class DocumentActionController(DocumentActionControllerInterface):
    async def execute_document_action(
            self,
            document_action_request: DocumentActionRequest,
            document_action_service: DocumentActionServiceInterface = Depends(get_document_action_service),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> DocumentActionResponse:
        logger.info(
            "Handling document action request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        document_action_response = await document_action_service.execute_document_action(
            document_action_request=document_action_request,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Document action completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return document_action_response


router = APIRouter()
document_action_controller = DocumentActionController()

router.post(
    "",
    response_model=DocumentActionResponse,
)(document_action_controller.execute_document_action)
