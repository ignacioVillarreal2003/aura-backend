import logging
from typing import Optional

from app.application.services.document_query_service.document_query_service import (
    DocumentQueryService
)
from app.application.services.document_query_service.document_query_service_settings import DocumentQueryServiceSettings
from app.application.services.document_query_service.interfaces.document_query_service_interface import (
    DocumentQueryServiceInterface
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_factory import (
    create_document_repository
)

logger = logging.getLogger(__name__)


def create_document_query_service(
        document_query_service_settings: Optional[DocumentQueryServiceSettings] = None,
        **config_kwargs
) -> DocumentQueryServiceInterface:
    try:
        logger.info("Creating DocumentQueryService instance")

        if document_query_service_settings is None:
            if config_kwargs:
                document_query_service_settings = DocumentQueryServiceSettings(
                    **config_kwargs
                )
            else:
                document_query_service_settings = DocumentQueryServiceSettings()

        document_repository = create_document_repository()

        return DocumentQueryService(
            document_repository=document_repository,
            document_query_service_settings=document_query_service_settings
        )

    except Exception as e:
        logger.exception("Failed to create DocumentQueryService")
        raise
