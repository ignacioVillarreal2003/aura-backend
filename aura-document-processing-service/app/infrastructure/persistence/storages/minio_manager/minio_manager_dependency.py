import logging
from fastapi import HTTPException, Request, status
from minio import Minio

from app.infrastructure.persistence.storages.minio_manager.exceptions.minio_manager_exception import (
    MinioManagerNotInitializedException
)
from app.infrastructure.persistence.storages.minio_manager.interfaces.minio_manager_interface import (
    MinioManagerInterface
)

logger = logging.getLogger(__name__)


async def get_minio_manager(request: Request) -> MinioManagerInterface:
    try:
        minio_manager: MinioManagerInterface = request.app.state.minio_manager
        if not minio_manager.is_started:
            logger.error("MinioManager found in app state but not started")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage (MinIO) not available"
            )
        return minio_manager
    except AttributeError:
        logger.error("MinioManager not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage not configured"
        )


async def get_minio_client(request: Request) -> Minio:
    try:
        minio_manager = await get_minio_manager(request)
        return minio_manager.client
    except MinioManagerNotInitializedException:
        logger.error("Minio client requested but manager is not started")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage (MinIO) not available"
        )
    except Exception:
        logger.exception("Unexpected error retrieving Minio client")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage error occurred"
        )
