from typing import Optional

from fastapi import APIRouter, File, UploadFile, Depends, Form, Header, HTTPException, status
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.document_controllers.create_document_controller.interfaces.create_document_controller_interface import (
    CreateDocumentControllerInterface
)
from app.application.services.document.create_document_service.create_document_service import (
    get_create_document_service
)
from app.application.services.document.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface
)
from app.domain.dtos.document.create_document.create_document_request import CreateDocumentRequest
from app.domain.dtos.document.create_document.create_document_response import CreateDocumentResponse
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.configuration.environment_variables import environment_variables
from app.infrastructure.http.authentication_provider.authentication_provider import get_authenticated_user
from app.infrastructure.persistence.database.database_manager.database_manager import get_database_session

logger = logging.getLogger(__name__)


class CreateDocumentController(CreateDocumentControllerInterface):
    async def create_document(
            self,
            create_document_request: CreateDocumentRequest = Depends(CreateDocumentRequest.as_form),
            raw_document: UploadFile = File(...),
            create_document_service: CreateDocumentServiceInterface = Depends(get_create_document_service),
            database_session: AsyncSession = Depends(get_database_session),
            authenticated_user: AuthenticatedUser = Depends(get_authenticated_user)
    ) -> CreateDocumentResponse:
        logger.info(
            "Handling create document request",
            extra={
                "user_id": authenticated_user.id
            }
        )

        create_document_response = await create_document_service.create_document(
            create_document_request=create_document_request,
            raw_document=raw_document,
            database_session=database_session,
            authenticated_user=authenticated_user
        )

        logger.info(
            "Create document completed successfully",
            extra={
                "user_id": authenticated_user.id
            }
        )

        return create_document_response

    async def create_document_internal(
            self,
            chat_id: int = Form(...),
            actor_user_id: int = Form(...),
            actor_email: str = Form(...),
            raw_document: UploadFile = File(...),
            x_internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
            create_document_service: CreateDocumentServiceInterface = Depends(get_create_document_service),
            database_session: AsyncSession = Depends(get_database_session),
    ) -> CreateDocumentResponse:
        if x_internal_token != environment_variables.service_api_key:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid internal token",
            )

        authenticated_user = AuthenticatedUser(
            id=actor_user_id,
            email=actor_email,
            roles=["admin"],
            permissions=["DOCUMENT_CREATE"],
        )

        create_document_request = CreateDocumentRequest(chat_id=chat_id)

        return await create_document_service.create_document(
            create_document_request=create_document_request,
            raw_document=raw_document,
            database_session=database_session,
            authenticated_user=authenticated_user,
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
