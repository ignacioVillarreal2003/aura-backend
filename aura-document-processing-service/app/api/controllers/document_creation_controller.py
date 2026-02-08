from fastapi import APIRouter, File, UploadFile, Depends, BackgroundTasks
from sqlalchemy.orm import Session
import logging

from app.api.controllers.interfaces.document_creation_controller_interface import DocumentCreationControllerInterface
from app.application.services.document_creation_service.interfaces.document_creation_service_interface import (
    DocumentCreationServiceInterface
)
from app.configuration.dependencies import get_database_session, get_document_creation_service
from app.domain.dtos.document_creation.document_creation_request import DocumentCreationRequest
from app.domain.dtos.document_creation.document_creation_response import DocumentCreationResponse
from app.infrastructure.authentication_provider.dependencies.authentication_provider_dependencies import (
    get_current_user
)
from app.infrastructure.authentication_provider.dtos.authentication_response import AuthenticationResponse

logger = logging.getLogger(__name__)


class DocumentCreationController(DocumentCreationControllerInterface):
    async def create_document(
            self,
            background_tasks: BackgroundTasks,
            document_creation_request: DocumentCreationRequest = Depends(DocumentCreationRequest.as_form),
            raw_document: UploadFile = File(...),
            document_creation_service: DocumentCreationServiceInterface = Depends(get_document_creation_service),
            db: Session = Depends(get_database_session),
            user: AuthenticationResponse = Depends(get_current_user)
    ) -> DocumentCreationResponse:
        logger.info("Processing document creation request")

        document_creation_response = await document_creation_service.create_document(
            document_creation_request=document_creation_request,
            raw_document=raw_document,
            background_tasks=background_tasks,
            db=db,
            user=user
        )

        logger.info("Document creation request processed successfully")

        return document_creation_response


router = APIRouter()

document_creation_controller = DocumentCreationController()

router.post(
    "",
    response_model=DocumentCreationResponse
)(document_creation_controller.create_document)
