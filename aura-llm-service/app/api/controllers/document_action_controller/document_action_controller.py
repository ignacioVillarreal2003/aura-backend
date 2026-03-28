import logging

from fastapi import APIRouter, Depends

from app.api.controllers.controller_logging import log_controller
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
            document_action_request: DocumentActionRequest,
            document_action_service: DocumentActionServiceInterface = Depends(get_document_action_service),
            authenticated_user: AuthenticationResponse = Depends(get_current_user),
    ) -> DocumentActionResponse:
        log_controller(
            logger,
            operation="execute_document_action",
            phase="start",
            user_id=authenticated_user.id,
            document_ids=document_action_request.document_ids,
            instruction_length=len(document_action_request.instruction or ""),
            action=document_action_request.action,
        )

        document_action_response = await document_action_service.execute_document_action(
            document_action_request=document_action_request,
            authenticated_user=authenticated_user,
        )

        log_controller(
            logger,
            operation="execute_document_action",
            phase="success",
            user_id=authenticated_user.id,
            document_ids=document_action_response.document_ids,
            action=document_action_response.action,
        )

        return document_action_response


router = APIRouter()

document_action_controller = DocumentActionController()

router.post(
    "",
    response_model=DocumentActionResponse,
)(document_action_controller.execute_document_action)
