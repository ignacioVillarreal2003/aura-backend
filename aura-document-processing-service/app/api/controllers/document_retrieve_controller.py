from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.interfaces.document_retrieve_controller_interface import DocumentRetrieveControllerInterface
from app.application.services.document_retrieve_service.document_retrieve_service_dependency import (
    get_document_retrieve_service
)
from app.application.services.document_retrieve_service.interfaces.document_retrieve_service_interface import (
    DocumentRetrieveServiceInterface
)
from app.domain.dtos.document_retrieve.context_fragments_response import ContextFragmentsResponse
from app.domain.dtos.document_retrieve.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.document_retrieve.question_context_fragments_request import QuestionContextFragmentsRequest
from app.infrastructure.persistence.database.database_manager.database_manager_dependency import get_database_session

logger = logging.getLogger(__name__)


class DocumentRetrieveController(DocumentRetrieveControllerInterface):
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            document_retrieve_service: DocumentRetrieveServiceInterface = Depends(get_document_retrieve_service),
            database_session: AsyncSession = Depends(get_database_session),
    ) -> ContextFragmentsResponse:
        logger.info("Processing question context fragments request")

        context_fragments_response = await document_retrieve_service.retrieve_context_fragments_by_question(
            question_context_fragments_request=question_context_fragments_request,
            database_session=database_session
        )

        logger.info("Question context fragments request processed successfully")

        return context_fragments_response

    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            document_retrieve_service: DocumentRetrieveServiceInterface = Depends(get_document_retrieve_service),
            database_session: AsyncSession = Depends(get_database_session),
    ) -> ContextFragmentsResponse:
        logger.info("Processing document context fragments request")

        context_fragments_response = await document_retrieve_service.retrieve_context_fragments_by_document(
            document_context_fragments_request=document_context_fragments_request,
            database_session=database_session
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
