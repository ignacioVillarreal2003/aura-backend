from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import logging

from app.api.interfaces.document_query_controller_interface import DocumentQueryControllerInterface
from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.configuration.dependencies import get_document_query_service, get_database_session
from app.domain.dtos.document_query.document_list_response import DocumentListResponse
from app.domain.dtos.document_query.document_response import DocumentResponse

logger = logging.getLogger(__name__)


class DocumentQueryController(DocumentQueryControllerInterface):
    async def get_document_by_id(
            self,
            document_id: int,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            db: Session = Depends(get_database_session)
    ) -> DocumentResponse:
        logger.info("Processing document deletion request")

        document_response = await document_query_service.get_document_by_id(
            document_id=document_id,
            db=db
        )

        logger.info("Document deletion request processed successfully")

        return document_response

    async def get_documents(
            self,
            page: Optional[int] = None,
            size: Optional[int] = None,
            document_query_service: DocumentQueryServiceInterface = Depends(get_document_query_service),
            db: Session = Depends(get_database_session)
    ) -> DocumentListResponse:
        logger.info("Processing document deletion request")

        document_list_response = await document_query_service.get_documents(
            page=page,
            size=size,
            db=db
        )

        logger.info("Document deletion request processed successfully")

        return document_list_response


router = APIRouter()

document_query_controller = DocumentQueryController()

router.get(
    "/document/{document_id}",
    response_model=DocumentResponse
)(document_query_controller.get_document_by_id)

router.get(
    "/documents",
    response_model=DocumentListResponse
)(document_query_controller.get_documents)
