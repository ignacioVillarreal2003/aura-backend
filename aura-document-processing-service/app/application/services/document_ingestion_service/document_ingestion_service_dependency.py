import logging
from fastapi import HTTPException, Request, status

from app.application.services.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface
)

logger = logging.getLogger(__name__)


async def get_document_ingestion_service(
        request: Request
) -> DocumentIngestionServiceInterface:
    try:
        document_ingestion_service: DocumentIngestionServiceInterface = request.app.state.document_ingestion_service
        return document_ingestion_service
    except AttributeError:
        logger.error("DocumentIngestionService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document ingestion service not configured"
        )
