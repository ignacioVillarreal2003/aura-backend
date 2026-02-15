import logging
from fastapi import HTTPException, Request, status

from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)

logger = logging.getLogger(__name__)


async def get_document_query_service(
        request: Request
) -> DocumentQueryServiceInterface:
    try:
        document_query_service: DocumentQueryServiceInterface = request.app.state.document_query_service
        return document_query_service

    except AttributeError:
        logger.error("DocumentQueryService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document query service not configured",
        )
