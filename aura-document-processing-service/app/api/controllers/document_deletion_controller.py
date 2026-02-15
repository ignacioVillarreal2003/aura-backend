from fastapi import APIRouter, Depends
from fastapi import Response, status
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.interfaces.document_deletion_controller_interface import DocumentDeletionControllerInterface
from app.application.services.document_deletion_service.document_deletion_service_dependency import (
    get_document_deletion_service
)
from app.application.services.document_deletion_service.interfaces.document_deletion_service_interface import (
    DocumentDeletionServiceInterface
)
from app.infrastructure.persistence.database.database_manager.database_manager_dependency import get_database_session
from app.infrastructure.authentication_provider.authentication_provider_dependency import (
    get_current_user
)
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse

logger = logging.getLogger(__name__)


class DocumentDeletionController(DocumentDeletionControllerInterface):
    async def soft_delete_document(
            self,
            document_id: int,
            document_deletion_service: DocumentDeletionServiceInterface = Depends(get_document_deletion_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> Response:
        logger.info("Processing document deletion request")

        await document_deletion_service.soft_delete_document(
            document_id=document_id,
            database_session=database_session,
            user=user
        )

        logger.info("Document deletion request processed successfully")

        return Response(
            status_code=status.HTTP_204_NO_CONTENT
        )

    async def hard_delete_document(
            self,
            document_id: int,
            document_deletion_service: DocumentDeletionServiceInterface = Depends(get_document_deletion_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> Response:
        logger.info("Processing document deletion request")

        await document_deletion_service.hard_delete_document(
            document_id=document_id,
            database_session=database_session,
            user=user
        )

        logger.info("Document deletion request processed successfully")

        return Response(
            status_code=status.HTTP_204_NO_CONTENT
        )


router = APIRouter()

document_deletion_controller = DocumentDeletionController()

router.post(
    "/soft",
    response_model=None
)(document_deletion_controller.soft_delete_document)

router.post(
    "/hard",
    response_model=None
)(document_deletion_controller.hard_delete_document)
