import logging
from fastapi import HTTPException, Request, status
from minio import Minio

from app.infrastructure.persistence.storages.minio_manager.interfaces.minio_manager_interface import (
    MinioManagerInterface
)
from app.infrastructure.persistence.storages.minio_manager.exceptions.minio_manager_exception import (
    MinioManagerNotInitializedException,
)

logger = logging.getLogger(__name__)


async def get_minio_manager(
        request: Request
) -> MinioManagerInterface:
    try:
        minio_manager: MinioManagerInterface = request.app.state.minio_manager

        if not minio_manager.is_started:
            logger.error("MinioManager found but not started")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage (MinIO) not available",
            )

        return minio_manager

    except AttributeError:
        logger.error("MinioManager not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage not configured",
        )


async def get_minio_client(
        request: Request
) -> Minio:
    try:
        manager = await get_minio_manager(request)
        return manager.client
    except MinioManagerNotInitializedException as e:
        logger.error(f"Minio client access error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Storage (MinIO) not available",
        )
    except Exception:
        logger.exception("Unexpected error while getting Minio client")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage error occurred",
        )
