import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.application.exceptions.app_exceptions import AppError
from app.application.services.document_question_service import DocumentQuestionService
from app.configuration.dependencies import get_document_question_service
from app.domain.dtos.document_question_request import DocumentQuestionRequest
from app.domain.dtos.document_question_response import DocumentQuestionResponse

logger = logging.getLogger(__name__)
router = APIRouter()


class DocumentQuestionController:
    async def execute_document_question(self,
                                        request_body: DocumentQuestionRequest,
                                        service: DocumentQuestionService = Depends(
                                            get_document_question_service)) -> DocumentQuestionResponse:
        try:
            response = await service.execute_document_question(request_body)
            logger.info("Document question processed successfully")
            return response
        except AppError as e:
            logger.warning(f"App error in controller: {e.message}")
            raise HTTPException(
                status_code=e.status_code,
                detail={
                    "error": e.code,
                    "message": e.message
                },
            )
        except Exception:
            logger.exception("Unexpected error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred while generating the response",
                }
            )


controller = DocumentQuestionController()
router.post("", response_model=DocumentQuestionResponse)(controller.execute_document_question)
