import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.services.document_ingestion_service.document_ingestion_service_configuration import (
    DocumentIngestionServiceConfiguration
)
from app.application.services.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface
)
from app.domain.constants.document_status import DocumentStatus
from app.domain.models.document import Document
from app.domain.models.fragment import Fragment
from app.infrastructure.persistence.repositories.document_repository.document_repository import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.repositories.exceptions.database_exceptions import DatabaseError
from app.infrastructure.persistence.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)

logger = logging.getLogger(__name__)


class DocumentIngestionService(DocumentIngestionServiceInterface):
    def __init__(
            self,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            reader_factory: ReaderFactory,
            text_cleaner_factory: TextCleanerFactory,
            text_splitter_factory: TextSplitterFactory,
            embedder_factory: EmbedderFactory,
            document_ingestion_service_configuration: DocumentIngestionServiceConfiguration
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._reader_factory = reader_factory
        self._cleaner_factory = text_cleaner_factory
        self._splitter_factory = text_splitter_factory
        self._embedder_factory = embedder_factory

        self._document_creation_service_configuration = document_ingestion_service_configuration or DocumentIngestionServiceConfiguration()

        logger.info("DocumentIngestionService initialized")

    @classmethod
    def create(
            cls,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            reader_factory: ReaderFactory,
            text_cleaner_factory: TextCleanerFactory,
            text_splitter_factory: TextSplitterFactory,
            embedder_factory: EmbedderFactory,
            text_cleaner_type: Optional[str] = None,
            text_splitter_type: Optional[str] = None,
            embedder_type: Optional[str] = None,
            split_size: Optional[int] = None,
            split_overlap: Optional[int] = None
    ) -> "DocumentIngestionService":
        config_kwargs = {}

        if text_cleaner_type is not None:
            config_kwargs['text_cleaner_type'] = text_cleaner_type
        if text_splitter_type is not None:
            config_kwargs['text_splitter_type'] = text_splitter_type
        if embedder_type is not None:
            config_kwargs['embedder_type'] = embedder_type
        if split_size is not None:
            config_kwargs['split_size'] = split_size
        if split_overlap is not None:
            config_kwargs['split_overlap'] = split_overlap

        document_ingestion_service_configuration = DocumentIngestionServiceConfiguration(
            **config_kwargs
        )

        return cls(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            reader_factory=reader_factory,
            text_cleaner_factory=text_cleaner_factory,
            text_splitter_factory=text_splitter_factory,
            embedder_factory=embedder_factory,
            document_ingestion_service_configuration=document_ingestion_service_configuration
        )

    def execute_document_creation(
            self,
            document: Document,
            db: Session,
            local_file_path: Path
    ) -> None:
        try:
            reader = self._reader_factory.get_reader(
                file_path=local_file_path
            )
            reader_result = reader.read(
                file_path=local_file_path
            )

            cleaner = self._cleaner_factory.get_text_cleaner(
                method=self._document_creation_service_configuration.text_cleaner_type
            )
            clean_result = cleaner.clean_text(
                text=reader_result
            )

            splitter = self._splitter_factory.get_text_splitter(
                method=self._document_creation_service_configuration.text_splitter_type
            )
            splitter_result = splitter.split_text(
                text=clean_result,
                size=self._document_creation_service_configuration.split_size,
                overlap=self._document_creation_service_configuration.split_overlap
            )

            embedder = self._embedder_factory.get_embedder(
                method=self._document_creation_service_configuration.embedder_type
            )
            embedder_result = embedder.embed_documents(
                texts=splitter_result
            )

            for idx in range(len(embedder_result)):
                fragment = Fragment(
                    document_id=document.id,
                    vector=embedder_result[idx],
                    content=splitter_result[idx],
                    fragment_index=idx,
                    created_by=document.created_by,
                    created_at=datetime.now(),
                )
                self._fragment_repository.create(
                    fragment,
                    db
                )

            document.text_cleaner_type = self._document_creation_service_configuration.text_cleaner_type
            document.text_splitter_type = self._document_creation_service_configuration.text_splitter_type
            document.embedder_type = self._document_creation_service_configuration.embedder_type
            document.split_size = self._document_creation_service_configuration.split_size
            document.split_overlap = self._document_creation_service_configuration.split_overlap
            document.status = DocumentStatus.done

            self._document_repository.update(
                document=document,
                db=db
            )

        except Exception as e:
            document.status = DocumentStatus.failed
            self._document_repository.update(
                document=document,
                db=db
            )
            logger.exception(
                f"Error processing document: {type(e).__name__}: {str(e)}",
                exc_info=True
            )
            raise DatabaseError("Error en la ingesta del documento") from e

        finally:
            try:
                if os.path.exists(local_file_path):
                    os.remove(local_file_path)
                    logger.info("Temporary file deleted")
            except Exception as e:
                logger.warning(
                    "Could not delete temporary file",
                    extra={
                        "error": str(e)
                    }
                )
