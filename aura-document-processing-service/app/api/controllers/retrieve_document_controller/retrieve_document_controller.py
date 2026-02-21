from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio.session import AsyncSession
import logging

from app.api.controllers.retrieve_document_controller.interfaces.retrieve_document_controller_interface import (
    RetrieveDocumentControllerInterface
)
from app.application.services.retrieve_document_service.retrieve_document_service_dependency import (
    get_retrieve_document_service
)
from app.application.services.retrieve_document_service.interfaces.retrieve_document_service_interface import (
    RetrieveDocumentServiceInterface
)
from app.domain.dtos.retrieve_document.context_fragments_response import ContextFragmentsResponse
from app.domain.dtos.retrieve_document.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.retrieve_document.question_context_fragments_request import QuestionContextFragmentsRequest
from app.infrastructure.persistence.database.database_manager.database_manager_dependency import get_database_session

logger = logging.getLogger(__name__)


class RetrieveDocumentController(RetrieveDocumentControllerInterface):
    async def retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            retrieve_document_service: RetrieveDocumentServiceInterface = Depends(get_retrieve_document_service),
            database_session: AsyncSession = Depends(get_database_session),
    ) -> ContextFragmentsResponse:
        logger.info("Received retrieve context fragments by question request")

        context_fragments_response = await retrieve_document_service.retrieve_context_fragments_by_question(
            question_context_fragments_request=question_context_fragments_request,
            database_session=database_session
        )

        logger.info("Retrieve context fragments by question request completed successfully")

        return context_fragments_response

    async def retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            retrieve_document_service: RetrieveDocumentServiceInterface = Depends(get_retrieve_document_service),
            database_session: AsyncSession = Depends(get_database_session),
    ) -> ContextFragmentsResponse:
        logger.info("Received retrieve context fragments by document request")

        context_fragments_response = await retrieve_document_service.retrieve_context_fragments_by_document(
            document_context_fragments_request=document_context_fragments_request,
            database_session=database_session
        )

        logger.info("Retrieve context fragments by document request completed successfully")

        return context_fragments_response


router = APIRouter()

retrieve_document_controller = RetrieveDocumentController()

router.post(
    "/question",
    response_model=ContextFragmentsResponse
)(retrieve_document_controller.retrieve_context_fragments_by_question)

router.post(
    "/document",
    response_model=ContextFragmentsResponse
)(retrieve_document_controller.retrieve_context_fragments_by_document)
