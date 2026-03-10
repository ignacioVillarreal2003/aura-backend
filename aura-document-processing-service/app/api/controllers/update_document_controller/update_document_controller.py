from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.update_document_controller.interfaces.update_document_controller_interface import (
    UpdateDocumentControllerInterface
)
from app.application.services.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface
)
from app.application.services.update_document_service.update_document_service_dependency import (
    get_update_document_service
)
from app.domain.dtos.update_document_controller.post_process_document_request import PostProcessDocumentRequest
from app.domain.dtos.update_document_controller.post_process_document_response import PostProcessDocumentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.authentication_provider.authentication_provider_dependency import get_current_user
from app.infrastructure.persistence.database.database_manager.database_manager_dependency import (
    get_database_session
)

logger = logging.getLogger(__name__)


class UpdateDocumentController(UpdateDocumentControllerInterface):
    async def post_process_document(
            self,
            document_id: int,
            post_process_document_request: PostProcessDocumentRequest,
            update_document_service: UpdateDocumentServiceInterface = Depends(get_update_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> PostProcessDocumentResponse:
        logger.info(
            "Post-process document request received",
            extra={
                "document_id": document_id,
                "user_id": user.id
            }
        )

        post_process_document_response = await update_document_service.post_process_document(
            document_id=document_id,
            post_process_document_request=post_process_document_request,
            database_session=database_session,
            user=user
        )

        logger.info(
            "Post-process document request completed",
            extra={
                "document_id": document_id,
                "user_id": user.id
            }
        )

        return post_process_document_response


router = APIRouter()

update_document_controller = UpdateDocumentController()

router.put(
    "/post-process/document/{document_id}",
    response_model=PostProcessDocumentResponse
)(update_document_controller.post_process_document)
