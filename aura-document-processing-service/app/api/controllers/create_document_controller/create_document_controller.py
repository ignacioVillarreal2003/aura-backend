from fastapi import APIRouter, File, UploadFile, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.create_document_controller.interfaces.create_document_controller_interface import (
    CreateDocumentControllerInterface
)
from app.application.services.create_document_service.create_document_service_dependency import (
    get_create_document_service
)
from app.application.services.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface
)
from app.domain.dtos.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.create_document.create_document_response import CreateDocumentResponse
from app.infrastructure.authentication_provider.authentication_provider_dependency import (
    get_current_user
)
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.database_manager.database_manager_dependency import get_database_session

logger = logging.getLogger(__name__)


class CreateDocumentController(CreateDocumentControllerInterface):
    async def create_document(
            self,
            background_tasks: BackgroundTasks,
            create_document_request: CreateDocumentRequest = Depends(CreateDocumentRequest.as_form),
            raw_document: UploadFile = File(...),
            create_document_service: CreateDocumentServiceInterface = Depends(get_create_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> CreateDocumentResponse:
        logger.info("Received document creation request")

        create_document_response = await create_document_service.create_document(
            create_document_request=create_document_request,
            raw_document=raw_document,
            background_tasks=background_tasks,
            database_session=database_session,
            user=user
        )

        logger.info("Document creation request completed successfully")

        return create_document_response


router = APIRouter()

create_document_controller = CreateDocumentController()

router.post(
    "",
    response_model=CreateDocumentResponse
)(create_document_controller.create_document)
