import logging
from fastapi import HTTPException, Request, status

from app.application.services.update_document_service.interfaces.update_document_service_interface import (
    UpdateDocumentServiceInterface
)

logger = logging.getLogger(__name__)


async def get_update_document_service(
        request: Request
) -> UpdateDocumentServiceInterface:
    try:
        update_document_service: UpdateDocumentServiceInterface = request.app.state.update_document_service
        return update_document_service

    except AttributeError:
        logger.error("UpdateDocumentService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Update document service not configured",
        )
