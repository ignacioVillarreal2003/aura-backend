import logging
from fastapi import APIRouter, Depends, HTTPException, status

from app.application.exceptions.app_exceptions import AppError
from app.application.services.document_summary_service import DocumentSummaryService
from app.configuration.dependencies import get_document_summary_service
from app.domain.dtos.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.document_summary_response import DocumentSummaryResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Document Summary"],
    responses={
        400: {"description": "Bad Request"},
        500: {"description": "Internal Server Error"}
    }
)


class DocumentSummaryController:
    async def execute_document_summary(self,
                                       request_body: DocumentSummaryRequest,
                                       document_summary_service: DocumentSummaryService = Depends(
                                           get_document_summary_service)) -> DocumentSummaryResponse:
        logger.info(
            "Processing document summary request",
            extra={
                "document_id": request_body.document_id
            }
        )

        try:
            response = await document_summary_service.execute_document_summary(request_body)

            logger.info(
                "Document summary request processed successfully",
                extra={
                    "document_id": request_body.document_id
                }
            )

            return response

        except AppError as e:
            logger.warning(
                "Application error in document summary controller",
                extra={
                    "error_code": e.code,
                    "error_message": e.message,
                    "status_code": e.status_code,
                    "document_id": request_body.document_id
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
                "Unexpected error in document summary controller",
                extra={
                    "error_type": type(e).__name__,
                    "document_id": request_body.document_id
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "InternalServerError",
                    "message": "An unexpected error occurred while processing the document summary request"
                }
            )


document_summary_controller = DocumentSummaryController()

router.post(
    "",
    response_model=DocumentSummaryResponse,
    summary="Execute a document summary request",
    description=(
        "Generates a structured and comprehensive summary for a specific document identified "
        "by its ID. The summarization process analyzes the document content to extract and "
        "condense the most relevant information."
    ),
    response_description=(
        "Returns a coherent and concise summary of the requested document, capturing its main "
        "ideas, key sections, and essential information."
    ),
    status_code=status.HTTP_200_OK
)(document_summary_controller.execute_document_summary)
