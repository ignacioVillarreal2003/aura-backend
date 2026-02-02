import logging
from typing import Optional
from asyncio import Lock

from app.infrastructure.persistence.storages.minio_client.minio_client import MinioClient

logger = logging.getLogger(__name__)

_global_minio_client: Optional[MinioClient] = None
_global_minio_client_lock = Lock()


async def get_global_minio_client(
        minio_endpoint: str,
        minio_access_key: str,
        minio_secret_key: str,
        minio_secure: Optional[bool] = None,
        minio_region: Optional[str] = None
) -> MinioClient:
    global _global_minio_client

    async with _global_minio_client_lock:
        if _global_minio_client is None:
            logger.info("Creating global MinioClient singleton")

            _global_minio_client = MinioClient.create(
                minio_endpoint=minio_endpoint,
                minio_access_key=minio_access_key,
                minio_secret_key=minio_secret_key,
                minio_secure=minio_secure,
                minio_region=minio_region
            )

            await _global_minio_client.start()
            logger.info("Global MinioClient started successfully")

        else:
            logger.debug("Returning existing global MinioClient")

    return _global_minio_client


async def shutdown_global_minio_client() -> None:
    global _global_minio_client

    async with _global_minio_client_lock:
        if _global_minio_client is not None:
            logger.info("Shutting down global MinioClient")
            await _global_minio_client.stop()
            _global_minio_client = None
            logger.info("Global MinioClient shut down successfully")
        else:
            logger.debug("Global MinioClient already shut down")
