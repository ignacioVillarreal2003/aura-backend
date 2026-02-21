import logging
from typing import Optional

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.services.retrieve_document_service.interfaces.retrieve_document_service_interface import (
    RetrieveDocumentServiceInterface
)
from app.application.services.retrieve_document_service.retrieve_document_service import RetrieveDocumentService
from app.application.services.retrieve_document_service.retrieve_document_service_settings import (
    RetrieveDocumentServiceSettings
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_factory import (
    create_fragment_repository
)

logger = logging.getLogger(__name__)


def create_retrieve_document_service(
        retrieve_document_service_settings: Optional[RetrieveDocumentServiceSettings] = None,
        **config_kwargs
) -> RetrieveDocumentServiceInterface:
    try:
        logger.info("Creating DocumentContextService instance")

        if retrieve_document_service_settings is None:
            if config_kwargs:
                retrieve_document_service_settings = RetrieveDocumentServiceSettings(
                    **config_kwargs
                )
            else:
                retrieve_document_service_settings = RetrieveDocumentServiceSettings()

        fragment_repository = create_fragment_repository()
        embedder_factory = EmbedderFactory()

        return RetrieveDocumentService(
            fragment_repository=fragment_repository,
            embedder_factory=embedder_factory,
            retrieve_document_service_settings=retrieve_document_service_settings
        )

    except Exception as e:
        logger.exception("Failed to create DocumentContextService")
        raise
