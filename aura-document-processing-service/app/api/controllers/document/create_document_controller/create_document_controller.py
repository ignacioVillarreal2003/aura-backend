from fastapi import APIRouter, File, UploadFile, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.controller_logging import log_controller
from app.api.controllers.document.create_document_controller.interfaces.create_document_controller_interface import (
    CreateDocumentControllerInterface
)
from app.application.services.create_document_service.create_document_service import get_create_document_service
from app.application.services.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface
)
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.document.create_document.create_document_response import CreateDocumentResponse
from app.domain.models.authenticated_user import AuthenticatedUser
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session

logger = logging.getLogger(__name__)


class CreateDocumentController(CreateDocumentControllerInterface):
    async def create_document(
            self,
            background_tasks: BackgroundTasks,
            create_document_request: CreateDocumentRequest = Depends(CreateDocumentRequest.as_form),
            raw_document: UploadFile = File(...),
            create_document_service: CreateDocumentServiceInterface = Depends(get_create_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> CreateDocumentResponse:
        log_controller(
            logger,
            operation="create_document",
            phase="start",
            user_id=authenticated_user.id,
            document_filename=raw_document.filename,
            content_type=raw_document.content_type,
        )

        create_document_response = await create_document_service.create_document(
            create_document_request=create_document_request,
            raw_document=raw_document,
            background_tasks=background_tasks,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        log_controller(
            logger,
            operation="create_document",
            phase="success",
            user_id=authenticated_user.id,
            document_id=create_document_response.id,
        )

        return create_document_response


router = APIRouter()

create_document_controller = CreateDocumentController()

router.post(
    "",
    response_model=CreateDocumentResponse
)(create_document_controller.create_document)
