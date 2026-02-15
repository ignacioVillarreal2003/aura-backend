import logging
from fastapi import HTTPException, Request, status

from app.application.services.document_retrieve_service.interfaces.document_retrieve_service_interface import (
    DocumentRetrieveServiceInterface
)

logger = logging.getLogger(__name__)


async def get_document_retrieve_service(
        request: Request
) -> DocumentRetrieveServiceInterface:
    try:
        document_context_service: DocumentRetrieveServiceInterface = request.app.state.document_context_service
        return document_context_service

    except AttributeError:
        logger.error("DocumentContextService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document context service not configured",
        )
