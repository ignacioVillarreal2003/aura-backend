from fastapi import APIRouter, File, UploadFile, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.interfaces.document_creation_controller_interface import DocumentCreationControllerInterface
from app.application.services.document_creation_service.document_creation_service_dependency import (
    get_document_creation_service
)
from app.application.services.document_creation_service.interfaces.document_creation_service_interface import (
    DocumentCreationServiceInterface
)
from app.domain.dtos.document_creation.document_creation_request import DocumentCreationRequest
from app.domain.dtos.document_creation.document_creation_response import DocumentCreationResponse
from app.domain.dtos.document_creation.document_creation_status_response import DocumentCreationStatusResponse
from app.infrastructure.authentication_provider.authentication_provider_dependency import (
    get_current_user
)
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.database_manager.database_manager_dependency import get_database_session

logger = logging.getLogger(__name__)


class DocumentCreationController(DocumentCreationControllerInterface):
    async def create_document(
            self,
            background_tasks: BackgroundTasks,
            document_creation_request: DocumentCreationRequest = Depends(DocumentCreationRequest.as_form),
            raw_document: UploadFile = File(...),
            document_creation_service: DocumentCreationServiceInterface = Depends(get_document_creation_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> DocumentCreationResponse:
        logger.info("Processing document creation request")

        document_creation_response = await document_creation_service.create_document(
            document_creation_request=document_creation_request,
            raw_document=raw_document,
            background_tasks=background_tasks,
            database_session=database_session,
            user=user
        )

        logger.info("Document creation request processed successfully")

        return document_creation_response

    async def get_document_creation_status(
            self,
            document_id: int,
            document_creation_service: DocumentCreationServiceInterface = Depends(get_document_creation_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> DocumentCreationStatusResponse:
        logger.info("Processing document creation request")

        document_creation_status_response = await document_creation_service.get_document_creation_status(
            document_id=document_id,
            database_session=database_session,
            user=user
        )

        logger.info("Document creation request processed successfully")

        return document_creation_status_response

router = APIRouter()

document_creation_controller = DocumentCreationController()

router.post(
    "",
    response_model=DocumentCreationResponse
)(document_creation_controller.create_document)

router.get(
    "/document/{document_id}",
    response_model=DocumentCreationStatusResponse
)(document_creation_controller.get_document_creation_status)
