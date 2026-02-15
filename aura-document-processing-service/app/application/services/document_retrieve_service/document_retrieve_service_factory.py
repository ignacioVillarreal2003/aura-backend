import logging
from typing import Optional

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.services.document_retrieve_service.document_retrieve_service import DocumentRetrieveService
from app.application.services.document_retrieve_service.document_retrieve_service_settings import (
    DocumentRetrieveServiceSettings
)
from app.application.services.document_retrieve_service.interfaces.document_retrieve_service_interface import (
    DocumentRetrieveServiceInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_factory import (
    create_fragment_repository
)

logger = logging.getLogger(__name__)


def create_document_retrieve_service(
        document_retrieve_service_settings: Optional[DocumentRetrieveServiceSettings] = None,
        **config_kwargs
) -> DocumentRetrieveServiceInterface:
    try:
        logger.info("Creating DocumentContextService instance")

        if document_retrieve_service_settings is None:
            if config_kwargs:
                document_retrieve_service_settings = DocumentRetrieveServiceSettings(
                    **config_kwargs
                )
            else:
                document_retrieve_service_settings = DocumentRetrieveServiceSettings()

        fragment_repository = create_fragment_repository()
        embedder_factory = EmbedderFactory()

        return DocumentRetrieveService(
            fragment_repository=fragment_repository,
            embedder_factory=embedder_factory,
            document_retrieve_service_settings=document_retrieve_service_settings
        )

    except Exception as e:
        logger.exception("Failed to create DocumentContextService")
        raise
