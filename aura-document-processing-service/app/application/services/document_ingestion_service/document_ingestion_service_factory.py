import logging
from typing import Optional

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.services.document_ingestion_service.document_ingestion_service import (
    DocumentIngestionService
)
from app.application.services.document_ingestion_service.document_ingestion_service_configuration import (
    DocumentIngestionServiceConfiguration
)

from app.application.services.document_ingestion_service.document_ingestion_service_settings import \
    DocumentIngestionServiceSettings
from app.application.services.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface
)
from app.infrastructure.persistence.database.database_manager.database_manager import (
    DatabaseManager
)
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import \
    DatabaseManagerInterface
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_factory import (
    create_document_repository
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_factory import (
    create_fragment_repository
)

logger = logging.getLogger(__name__)


def create_document_ingestion_service(
        database_manager: DatabaseManagerInterface,
        document_ingestion_service_settings: Optional[DocumentIngestionServiceSettings] = None,
        **config_kwargs
) -> DocumentIngestionServiceInterface:
    try:
        logger.info("Creating DocumentIngestionService instance")

        if document_ingestion_service_settings is None:
            if config_kwargs:
                document_ingestion_service_settings = DocumentIngestionServiceSettings(
                    **config_kwargs
                )
            else:
                document_ingestion_service_settings = DocumentIngestionServiceSettings()

        document_repository = create_document_repository()
        fragment_repository = create_fragment_repository()

        reader_factory = ReaderFactory()
        text_cleaner_factory = TextCleanerFactory()
        text_splitter_factory = TextSplitterFactory()
        embedder_factory = EmbedderFactory()

        return DocumentIngestionService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            reader_factory=reader_factory,
            text_cleaner_factory=text_cleaner_factory,
            text_splitter_factory=text_splitter_factory,
            embedder_factory=embedder_factory,
            database_manager=database_manager,
            document_ingestion_service_settings=document_ingestion_service_settings
        )

    except Exception as e:
        logger.exception("Failed to create DocumentIngestionService")
        raise
