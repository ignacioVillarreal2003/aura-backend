import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.exceptions.exceptions import NotFoundError, DatabaseError, StorageError
from app.application.services.interfaces.storage_service_interface import StorageServiceInterface
from app.domain.models.document import Document
from app.domain.models.fragment import Fragment
from app.application.services.interfaces.ingestion_service_interface import IngestionServiceInterface
from app.infrastructure.persistence.repositories.interfaces.document_repository_interface import DocumentRepositoryInterface
from app.infrastructure.persistence.repositories.interfaces.fragment_repository_interface import FragmentRepositoryInterface


logger = logging.getLogger(__name__)


class IngestionService(IngestionServiceInterface):
    def __init__(self,
                 document_repository: DocumentRepositoryInterface,
                 fragment_repository: FragmentRepositoryInterface,
                 storage_service: StorageServiceInterface):
        self.document_repository = document_repository
        self.fragment_repository = fragment_repository
        self.storage_service = storage_service
        self.reader_factory = ReaderFactory()
        self.cleaner_factory = TextCleanerFactory()
        self.splitter_factory = TextSplitterFactory()

    def process_document(self,
                         document_id: int,
                         db: Session,
                         cleaner_type: str = "basic",
                         splitter_type: str = "recursive",
                         split_size: int = 500,
                         split_overlap: int = 50,
                         download_dir: Optional[Path] = None) -> None:
        document: Optional[Document] = self.document_repository.get_by_id(document_id, db)
        if document is None:
            logger.warning(f"Document {document_id} not found")
            raise NotFoundError("Document not found")
        if not document.path:
            logger.error(f"Document {document_id} has no storage path")
            raise DatabaseError("Document has no storage path")

        try:
            local_file_path: Path = self.storage_service.download_document(document.path, download_dir)
            logger.info(f"Downloaded document {document_id} to {local_file_path}")
        except StorageError as e:
            logger.exception("Failed to download document")
            raise

        try:
            reader = self.reader_factory.get_reader(local_file_path)
            raw_text = reader.read(local_file_path)
        except Exception as e:
            logger.exception("Failed to read document")
            raise DatabaseError("Failed to read document") from e

        try:
            cleaner = self.cleaner_factory.get_cleaner(cleaner_type)
            clean_text = cleaner.clean_text(raw_text)
        except Exception as e:
            logger.exception("Failed to clean document text")
            raise DatabaseError("Failed to clean document text") from e

        try:
            splitter = self.splitter_factory.get_splitter(splitter_type)
            splits = splitter.split_text(clean_text, size=split_size, overlap=split_overlap)
        except Exception as e:
            logger.exception("Failed to split document text")
            raise DatabaseError("Failed to split document text") from e

        for idx, content in enumerate(splits):
            fragment = Fragment(
                document_id=document.id,
                content=content,
                fragment_index=idx,
                chunk_size=split_size,
                created_by=document.created_by,
                created_at=datetime.now()
            )
            try:
                self.fragment_repository.create(fragment, db)
                logger.debug(f"Persisted fragment {idx} for document {document_id}")
            except Exception as e:
                logger.exception(f"Failed to persist fragment {idx}")
                raise DatabaseError(f"Failed to persist fragment {idx}") from e

        logger.info(f"Document {document_id} ingested successfully with {len(splits)} fragments")