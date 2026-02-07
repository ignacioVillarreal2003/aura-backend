from fastapi import APIRouter, Depends
from fastapi import Response, status
from sqlalchemy.orm import Session
import logging

from app.api.interfaces.document_deletion_controller_interface import DocumentDeletionControllerInterface
from app.application.services.document_deletion_service.interfaces.document_deletion_service_interface import (
    DocumentDeletionServiceInterface
)
from app.configuration.dependencies import get_database_session, get_document_deletion_service

logger = logging.getLogger(__name__)


class DocumentDeletionController(DocumentDeletionControllerInterface):
    async def soft_delete_document(
            self,
            document_id: int,
            document_deletion_service: DocumentDeletionServiceInterface = Depends(get_document_deletion_service),
            db: Session = Depends(get_database_session)
    ) -> Response:
        logger.info("Processing document deletion request")

        await document_deletion_service.soft_delete_document(
            document_id=document_id,
            db=db
        )

        logger.info("Document deletion request processed successfully")

        return Response(
            status_code=status.HTTP_204_NO_CONTENT
        )

    async def hard_delete_document(
            self,
            document_id: int,
            document_deletion_service: DocumentDeletionServiceInterface = Depends(get_document_deletion_service),
            db: Session = Depends(get_database_session)
    ) -> Response:
        logger.info("Processing document deletion request")

        await document_deletion_service.hard_delete_document(
            document_id=document_id,
            db=db
        )

        logger.info("Document deletion request processed successfully")

        return Response(
            status_code=status.HTTP_204_NO_CONTENT
        )


router = APIRouter()

document_deletion_controller = DocumentDeletionController()

router.post(
    "/soft",
    response_model=Response
)(document_deletion_controller.soft_delete_document)

router.post(
    "/hard",
    response_model=Response
)(document_deletion_controller.hard_delete_document)
