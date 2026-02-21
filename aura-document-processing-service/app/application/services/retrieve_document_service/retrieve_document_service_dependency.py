import logging
from fastapi import HTTPException, Request, status

from app.application.services.retrieve_document_service.interfaces.retrieve_document_service_interface import (
    RetrieveDocumentServiceInterface
)

logger = logging.getLogger(__name__)


async def get_retrieve_document_service(
        request: Request
) -> RetrieveDocumentServiceInterface:
    try:
        retrieve_document_service: RetrieveDocumentServiceInterface = request.app.state.retrieve_document_service
        return retrieve_document_service

    except AttributeError:
        logger.error("DocumentRetrieveService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document retrieve service not configured",
        )
