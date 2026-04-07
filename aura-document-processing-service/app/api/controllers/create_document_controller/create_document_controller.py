from typing import Optional

from fastapi import APIRouter, File, UploadFile, Depends, BackgroundTasks, Form, Header, HTTPException, status
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.create_document_controller.interfaces.create_document_controller_interface import (
    CreateDocumentControllerInterface
)
from app.application.services.create_document_service.create_document_service import get_create_document_service
from app.application.services.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface
)
from app.domain.dtos.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.create_document.create_document_response import CreateDocumentResponse
from app.infrastructure.authentication_provider.authentication_provider import get_current_user
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session
from app.configuration.environment_variables import environment_variables

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
        logger.info(
            "Create document request received",
            extra={
                "filename_document": raw_document.filename,
                "content_type": raw_document.content_type,
                "user_id": user.id
            }
        )

        create_document_response = await create_document_service.create_document(
            create_document_request=create_document_request,
            raw_document=raw_document,
            background_tasks=background_tasks,
            database_session=database_session,
            user=user
        )

        logger.info(
            "Create document request completed",
            extra={
                "document_id": create_document_response.id,
                "user_id": user.id
            }
        )

        return create_document_response

    async def create_document_internal(
            self,
            background_tasks: BackgroundTasks,
            chat_id: int = Form(...),
            actor_user_id: int = Form(...),
            actor_email: str = Form(...),
            raw_document: UploadFile = File(...),
            x_internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
            create_document_service: CreateDocumentServiceInterface = Depends(get_create_document_service),
            database_session: AsyncSession = Depends(get_database_session),
    ) -> CreateDocumentResponse:
        if x_internal_token != environment_variables.document_internal_api_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid internal token",
            )

        user = AuthenticationResponse(
            id=actor_user_id,
            email=actor_email,
            roles=["admin"],
            permissions=["DOCUMENT_CREATE"],
        )
        create_document_request = CreateDocumentRequest(chat_id=chat_id)

        return await create_document_service.create_document(
            create_document_request=create_document_request,
            raw_document=raw_document,
            background_tasks=background_tasks,
            database_session=database_session,
            user=user,
        )


router = APIRouter()

create_document_controller = CreateDocumentController()

router.post(
    "",
    response_model=CreateDocumentResponse
)(create_document_controller.create_document)

router.post(
    "/internal",
    response_model=CreateDocumentResponse,
)(create_document_controller.create_document_internal)