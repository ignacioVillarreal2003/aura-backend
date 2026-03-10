import logging
from fastapi import HTTPException, Request, status

from app.application.services.delete_document_service.interfaces.delete_document_service_interface import (
    DeleteDocumentServiceInterface
)

logger = logging.getLogger(__name__)


async def get_delete_document_service(request: Request) -> DeleteDocumentServiceInterface:
    try:
        return request.app.state.delete_document_service
    except AttributeError:
        logger.error("DeleteDocumentService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DeleteDocumentService not configured"
        )
