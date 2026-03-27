import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request

from app.api.controllers.document_action_controller.interfaces.document_action_controller_interface import (
    DocumentActionControllerInterface,
)
from app.application.services.document_action_service.document_action_service import get_document_action_service
from app.application.services.document_action_service.interfaces.document_action_service_interface import (
    DocumentActionServiceInterface,
)
from app.domain.dtos.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.document_action.document_action_response import DocumentActionResponse
from app.infrastructure.authentication_provider.authentication_provider import get_current_user
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse

logger = logging.getLogger(__name__)


class DocumentActionController(DocumentActionControllerInterface):
    async def execute_document_action(
            self,
            request: Request,
            document_action_request: DocumentActionRequest,
            document_action_service: DocumentActionServiceInterface = Depends(get_document_action_service),
            authenticated_user: AuthenticationResponse = Depends(get_current_user),
    ) -> DocumentActionResponse:
        logger.info(
            "Execute document action request received",
            extra={"user_id": authenticated_user.id},
        )

        authorization_token: Optional[str] = request.headers.get("Authorization")

        document_action_response = await document_action_service.execute_document_action(
            document_action_request=document_action_request,
            authenticated_user=authenticated_user,
            authorization_token=authorization_token,
        )

        logger.info(
            "Execute document action request completed",
            extra={"user_id": authenticated_user.id},
        )

        return document_action_response


router = APIRouter()

document_action_controller = DocumentActionController()

router.post(
    "",
    response_model=DocumentActionResponse,
)(document_action_controller.execute_document_action)
