import logging
from fastapi import HTTPException, Request, status

from app.application.services.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface
)

logger = logging.getLogger(__name__)


async def get_update_document_service(request: Request) -> UpdateDocumentServiceInterface:
    try:
        return request.app.state.update_document_service
    except AttributeError:
        logger.error("UpdateDocumentService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="UpdateDocumentService not configured",
        )
