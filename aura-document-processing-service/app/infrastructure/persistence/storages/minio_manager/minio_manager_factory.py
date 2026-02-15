import logging
from typing import Optional

from app.infrastructure.persistence.storages.minio_manager.minio_manager import MinioManager
from app.infrastructure.persistence.storages.minio_manager.minio_manager_settings import MinioManagerSettings
from app.infrastructure.persistence.storages.minio_manager.interfaces.minio_manager_interface import (
    MinioManagerInterface,
)

logger = logging.getLogger(__name__)


def create_minio_manager(
        minio_endpoint: Optional[str],
        minio_access_key: Optional[str],
        minio_secret_key: Optional[str],
        minio_manager_settings: Optional[MinioManagerSettings] = None,
        **config_kwargs
) -> MinioManagerInterface:
    try:
        logger.info("Creating MinioManager instance")

        if minio_manager_settings is None:
            if minio_endpoint and minio_access_key and minio_secret_key:
                minio_manager_settings = MinioManagerSettings(
                    endpoint=minio_endpoint,
                    access_key=minio_access_key,
                    secret_key=minio_secret_key,
                    **config_kwargs
                )

            elif config_kwargs:
                minio_manager_settings = MinioManagerSettings(
                    **config_kwargs
                )

            else:
                raise Exception("MinioManager settings not provided")


        return MinioManager(
            minio_manager_settings=minio_manager_settings
        )

    except Exception:
        logger.exception("Failed to create MinioManager")
        raise
