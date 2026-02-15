import logging
from fastapi import HTTPException, Request, status

from app.application.services.document_deletion_service.interfaces.document_deletion_service_interface import (
    DocumentDeletionServiceInterface
)

logger = logging.getLogger(__name__)


async def get_document_deletion_service(
        request: Request
) -> DocumentDeletionServiceInterface:
    try:
        document_deletion_service: DocumentDeletionServiceInterface = request.app.state.document_deletion_service
        return document_deletion_service

    except AttributeError:
        logger.error("DocumentDeletionService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document deletion service not configured",
        )
