import logging
from fastapi import HTTPException, Request, status

from app.application.services.document_creation_service.interfaces.document_creation_service_interface import (
    DocumentCreationServiceInterface
)

logger = logging.getLogger(__name__)


async def get_document_creation_service(
        request: Request
) -> DocumentCreationServiceInterface:
    try:
        document_creation_service: DocumentCreationServiceInterface = request.app.state.document_creation_service
        return document_creation_service

    except AttributeError:
        logger.error("DocumentCreationService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document creation service not configured",
        )
