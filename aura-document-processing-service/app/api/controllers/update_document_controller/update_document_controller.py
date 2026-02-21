from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.update_document_controller.interfaces.update_document_controller_interface import (
    UpdateDocumentControllerInterface
)
from app.application.services.update_document_service.document_update_service_dependency import (
    get_update_document_service
)
from app.application.services.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface
)
from app.domain.dtos.update_document.update_document_request import UpdateDocumentRequest
from app.domain.dtos.update_document.update_document_response import UpdateDocumentResponse
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.database_manager.database_manager_dependency import get_database_session

logger = logging.getLogger(__name__)


class UpdateDocumentController(UpdateDocumentControllerInterface):
    async def update_document(
            self,
            document_id: int,
            update_document_request: UpdateDocumentRequest,
            update_document_service: UpdateDocumentServiceInterface = Depends(get_update_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends()
    ) -> UpdateDocumentResponse:
        logger.info(f"Received update document request")

        update_document_response = await update_document_service.update_document(
            document_id=document_id,
            update_document_request=update_document_request,
            database_session=database_session,
            user=user
        )

        logger.info(f"Update document request completed successfully")

        return update_document_response


router = APIRouter()

update_document_controller = UpdateDocumentController()

router.put(
    "/{document_id}",
    response_model=UpdateDocumentResponse
)(update_document_controller.update_document)
