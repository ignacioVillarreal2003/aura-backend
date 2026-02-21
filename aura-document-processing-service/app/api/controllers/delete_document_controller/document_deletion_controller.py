from fastapi import APIRouter, Depends
from fastapi import Response, status
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.delete_document_controller.interfaces.delete_document_controller_interface import (
    DeleteDocumentControllerInterface
)
from app.application.services.delete_document_service.delete_document_service_dependency import (
    get_delete_document_service
)
from app.application.services.delete_document_service.interfaces.delete_document_service_interface import (
    DeleteDocumentServiceInterface
)
from app.infrastructure.persistence.database.database_manager.database_manager_dependency import get_database_session
from app.infrastructure.authentication_provider.authentication_provider_dependency import (
    get_current_user
)
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse

logger = logging.getLogger(__name__)


class DeleteDocumentController(DeleteDocumentControllerInterface):
    async def soft_delete_document(
            self,
            document_id: int,
            delete_document_service: DeleteDocumentServiceInterface = Depends(get_delete_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> Response:
        logger.info(f"Received soft delete request")

        await delete_document_service.soft_delete_document(
            document_id=document_id,
            database_session=database_session,
            user=user
        )

        logger.info(f"Soft delete request completed successfully")

        return Response(
            status_code=status.HTTP_204_NO_CONTENT
        )

    async def hard_delete_document(
            self,
            document_id: int,
            delete_document_service: DeleteDocumentServiceInterface = Depends(get_delete_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> Response:
        logger.info(f"Received hard delete request")

        await delete_document_service.hard_delete_document(
            document_id=document_id,
            database_session=database_session,
            user=user
        )

        logger.info(f"Hard delete request completed successfully")

        return Response(
            status_code=status.HTTP_204_NO_CONTENT
        )


router = APIRouter()

delete_document_controller = DeleteDocumentController()

router.delete(
    "/soft/{document_id}",
    response_model=None
)(delete_document_controller.soft_delete_document)

router.delete(
    "/hard/{document_id}",
    response_model=None
)(delete_document_controller.hard_delete_document)
