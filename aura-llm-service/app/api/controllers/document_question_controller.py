import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.application.exceptions.app_exceptions import AppError
from app.application.services.document_question_service import DocumentQuestionService
from app.configuration.dependencies import get_document_question_service
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Document Question"],
    responses={
        400: {"description": "Bad Request"},
        500: {"description": "Internal Server Error"}
    }
)


class DocumentQuestionController:
    async def execute_document_question(self,
                                        request_body: DocumentQuestionRequest,
                                        document_question_service: DocumentQuestionService = Depends(
                                            get_document_question_service)) -> DocumentQuestionResponse:
        logger.info(
            "Processing document question request",
            extra={
                "question": request_body.question
            }
        )

        try:
            response = await document_question_service.execute_document_question(request_body)

            logger.info(
                "Document question request processed successfully",
                extra={
                    "question": request_body.question
                }
            )

            return response

        except AppError as e:
            logger.warning(
                "Application error in document question controller",
                extra={
                    "error_code": e.code,
                    "error_message": e.message,
                    "status_code": e.status_code,
                    "question": request_body.question
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
                    "error_type": type(e).__name__,
                    "question": request_body.question
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred while processing the document question request"
                }
            )


document_question_controller = DocumentQuestionController()

router.post(
    "",
    response_model=DocumentQuestionResponse,
    summary="Execute a document question request",
    description="Processes a question about document content",
    response_description="Respond with an document question response",
    status_code=status.HTTP_200_OK
)(document_question_controller.execute_document_question)
