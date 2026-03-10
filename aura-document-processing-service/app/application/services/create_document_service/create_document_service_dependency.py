import logging
from fastapi import HTTPException, Request, status

from app.application.services.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface
)

logger = logging.getLogger(__name__)


async def get_create_document_service(request: Request) -> CreateDocumentServiceInterface:
    try:
        return request.app.state.create_document_service
    except AttributeError:
        logger.error("CreateDocumentService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Create document service not configured"
        )
