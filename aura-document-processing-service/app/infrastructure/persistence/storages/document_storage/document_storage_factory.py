import logging
from typing import Optional

from app.infrastructure.persistence.storages.document_storage.document_storage import (
    DocumentStorage
)
from app.infrastructure.persistence.storages.document_storage.document_storage_settings import DocumentStorageSettings
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)
from app.infrastructure.persistence.storages.minio_manager.interfaces.minio_manager_interface import (
    MinioManagerInterface
)

logger = logging.getLogger(__name__)


def create_document_storage(
        minio_manager: MinioManagerInterface,
        document_storage_settings: Optional[DocumentStorageSettings] = None,
        **config_kwargs
) -> DocumentStorageInterface:
    try:
        logger.info("Creating DocumentStorage instance")

        if document_storage_settings is None:
            document_storage_settings = DocumentStorageSettings(
                **config_kwargs
            )

        return DocumentStorage(
            minio_manager=minio_manager,
            document_storage_settings=document_storage_settings
        )

    except Exception as e:
        logger.exception("Failed to create DocumentStorage")
        raise
