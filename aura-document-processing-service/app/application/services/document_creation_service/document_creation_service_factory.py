import logging
from typing import Optional

from app.application.services.document_creation_service.document_creation_service import (
    DocumentCreationService
)
from app.application.services.document_creation_service.document_creation_service_settings import (
    DocumentCreationServiceSettings
)
from app.application.services.document_creation_service.interfaces.document_creation_service_interface import (
    DocumentCreationServiceInterface
)
from app.application.services.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_factory import (
    create_document_repository
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)

logger = logging.getLogger(__name__)


def create_document_creation_service(
        document_storage: DocumentStorageInterface,
        document_ingestion_service: DocumentIngestionServiceInterface,
        document_creation_service_settings: Optional[DocumentCreationServiceSettings] = None,
        **config_kwargs
) -> DocumentCreationServiceInterface:
    try:
        logger.info("Creating DocumentCreationService instance")

        if document_creation_service_settings is None:
            if config_kwargs:
                document_creation_service_settings = DocumentCreationServiceSettings(
                    **config_kwargs
                )
            else:
                document_creation_service_settings = DocumentCreationServiceSettings()

        document_repository = create_document_repository()

        return DocumentCreationService(
            document_repository=document_repository,
            document_storage=document_storage,
            document_ingestion_service=document_ingestion_service,
            document_creation_service_settings=document_creation_service_settings
        )

    except Exception as e:
        logger.exception("Failed to create DocumentCreationService")
        raise
