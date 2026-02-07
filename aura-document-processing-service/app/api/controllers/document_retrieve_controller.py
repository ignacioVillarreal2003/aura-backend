from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import logging

from app.api.interfaces.document_retrieve_controller_interface import DocumentRetrieveControllerInterface
from app.application.services.document_retrieve_service.interfaces.document_context_service_interface import (
    DocumentContextServiceInterface
)
from app.configuration.dependencies import get_document_context_service, get_database_session
from app.domain.dtos.document_retrieve.context_fragments_response import ContextFragmentsResponse
from app.domain.dtos.document_retrieve.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.document_retrieve.question_context_fragments_request import QuestionContextFragmentsRequest

logger = logging.getLogger(__name__)


class DocumentRetrieveController(DocumentRetrieveControllerInterface):
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            document_context_service: DocumentContextServiceInterface = Depends(get_document_context_service),
            db: Session = Depends(get_database_session)
    ) -> ContextFragmentsResponse:
        logger.info("Processing question context fragments request")

        context_fragments_response = await document_context_service.retrieve_context_fragments_by_question(
            question_context_fragments_request=question_context_fragments_request,
            db=db
        )

        logger.info("Question context fragments request processed successfully")

        return context_fragments_response

    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            document_context_service: DocumentContextServiceInterface = Depends(get_document_context_service),
            db: Session = Depends(get_database_session)
    ) -> ContextFragmentsResponse:
        logger.info("Processing document context fragments request")

        context_fragments_response = await document_context_service.retrieve_context_fragments_by_document(
            document_context_fragments_request=document_context_fragments_request,
            db=db
        )

        logger.info("Document context fragments request processed successfully")

        return context_fragments_response


router = APIRouter()

document_context_controller = DocumentRetrieveController()

router.post(
    "/question",
    response_model=ContextFragmentsResponse
)(document_context_controller.retrieve_context_fragments_by_question)

router.post(
    "/document",
    response_model=ContextFragmentsResponse
)(document_context_controller.retrieve_context_fragments_by_document)
