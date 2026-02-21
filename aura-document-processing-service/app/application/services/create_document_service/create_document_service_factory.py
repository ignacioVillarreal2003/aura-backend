import logging
from typing import Optional

from app.application.services.create_document_service.create_document_service import CreateDocumentService
from app.application.services.create_document_service.create_document_service_settings import (
    CreateDocumentServiceSettings
)
from app.application.services.create_document_service.interfaces.create_document_service_interface import (
    CreateDocumentServiceInterface
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


def create_create_document_service(
        document_storage: DocumentStorageInterface,
        document_ingestion_service: DocumentIngestionServiceInterface,
        create_document_service_settings: Optional[CreateDocumentServiceSettings] = None,
        **config_kwargs
) -> CreateDocumentServiceInterface:
    try:
        logger.info("Creating DocumentCreationService instance")

        if create_document_service_settings is None:
            if config_kwargs:
                create_document_service_settings = CreateDocumentServiceSettings(
                    **config_kwargs
                )
            else:
                create_document_service_settings = CreateDocumentServiceSettings()

        document_repository = create_document_repository()

        return CreateDocumentService(
            document_repository=document_repository,
            document_storage=document_storage,
            document_ingestion_service=document_ingestion_service,
            create_document_service_settings=create_document_service_settings
        )

    except Exception as e:
        logger.exception("Failed to create DocumentCreationService")
        raise
