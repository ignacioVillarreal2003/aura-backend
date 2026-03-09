import logging
from fastapi import HTTPException, Request, status

from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)

logger = logging.getLogger(__name__)


async def get_document_storage(request: Request) -> DocumentStorageInterface:
    try:
        return request.app.state.document_storage
    except AttributeError:
        logger.error("DocumentStorage not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentStorage service not configured"
        )
