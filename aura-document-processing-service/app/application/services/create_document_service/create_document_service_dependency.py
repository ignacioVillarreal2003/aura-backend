import logging
from fastapi import HTTPException, Request, status

from app.application.services.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface
)

logger = logging.getLogger(__name__)


async def get_create_document_service(
        request: Request
) -> CreateDocumentServiceInterface:
    try:
        create_document_service: CreateDocumentServiceInterface = request.app.state.create_document_service
        return create_document_service

    except AttributeError:
        logger.error("DocumentCreationService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document creation service not configured",
        )
