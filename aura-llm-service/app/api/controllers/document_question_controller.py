import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.application.exceptions.app_exceptions import AppError
from app.application.services.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface
)
from app.configuration.dependencies import get_document_question_service
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse

logger = logging.getLogger(__name__)


class DocumentQuestionController:
    @staticmethod
    async def execute_document_question(document_question_request: DocumentQuestionRequest,
                                        document_question_service: DocumentQuestionServiceInterface = Depends(
                                            get_document_question_service)) -> DocumentQuestionResponse:
        logger.info("Processing document question request")

        try:
            document_question_response = await document_question_service.execute_document_question(document_question_request)

            logger.info("Document question request processed successfully")

            return document_question_response

        except AppError as e:
            logger.warning(
                "Application error in document question controller",
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
                "Unexpected error in document question controller",
                extra={
                    "error_type": type(e).__name__
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred while processing the document question request"
                }
            )


router = APIRouter()

document_question_controller = DocumentQuestionController()

router.post(
    "",
    response_model=DocumentQuestionResponse
)(document_question_controller.execute_document_question)
