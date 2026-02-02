from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from app.api.interfaces.document_context_controller_interface import DocumentContextControllerInterface
from app.application.exceptions.app_exception import AppError
from app.application.services.document_context_service.interfaces.document_context_service_interface import (
    DocumentContextServiceInterface
)
from app.configuration.dependencies import get_document_context_service, get_database_session
from app.domain.dtos.context_fragments_response import ContextFragmentsResponse
from app.domain.dtos.document_context_fragments_request import DocumentContextFragmentsRequest
from app.domain.dtos.question_context_fragments_request import QuestionContextFragmentsRequest

logger = logging.getLogger(__name__)


class DocumentContextController(DocumentContextControllerInterface):
    async def execute_retrieve_context_fragments_by_question(
            self,
            question_context_fragments_request: QuestionContextFragmentsRequest,
            document_context_service: DocumentContextServiceInterface = Depends(get_document_context_service),
            db: Session = Depends(get_database_session)
    ) -> ContextFragmentsResponse:
        logger.info("Processing question context fragments request")

        try:
            context_fragments_response = await document_context_service.execute_retrieve_context_fragments_by_question(
                question_context_fragments_request=question_context_fragments_request,
                db=db
            )

            logger.info("Question context fragments request processed successfully")

            return context_fragments_response

        except AppError as e:
            logger.warning(
                "Application error occurred while processing the question context fragments request",
                extra={
                    "error_code": e.code,
                    "error_message": e.message,
                    "status_code": e.status_code
                }
            )
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": e.code,
                    "message": e.message
                }
            )

        except Exception as e:
            logger.exception(
                "Unexpected error occurred while processing the question context fragments request",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred while processing the question context fragments request"
                }
            )

    async def execute_retrieve_context_fragments_by_document(
            self,
            document_context_fragments_request: DocumentContextFragmentsRequest,
            document_context_service: DocumentContextServiceInterface = Depends(get_document_context_service),
            db: Session = Depends(get_database_session)
    ) -> ContextFragmentsResponse:
        logger.info("Processing document context fragments request")

        try:
            context_fragments_response = await document_context_service.execute_retrieve_context_fragments_by_document(
                document_context_fragments_request=document_context_fragments_request,
                db=db
            )

            logger.info("Document context fragments request processed successfully")

            return context_fragments_response

        except AppError as e:
            logger.warning(
                "Application error occurred while processing the document context fragments request",
                extra={
                    "error_code": e.code,
                    "error_message": e.message,
                    "status_code": e.status_code
                }
            )
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": e.code,
                    "message": e.message
                }
            )

        except Exception as e:
            logger.exception(
                "Unexpected error occurred while processing the document context fragments request",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred while processing the document context fragments request"
                }
            )


router = APIRouter()

document_context_controller = DocumentContextController()

router.post(
    "/question",
    response_model=ContextFragmentsResponse
)(document_context_controller.execute_retrieve_context_fragments_by_question)

router.post(
    "/document",
    response_model=ContextFragmentsResponse
)(document_context_controller.execute_retrieve_context_fragments_by_document)
