import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, BinaryIO
from sqlalchemy.orm import Session

from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.exceptions.exceptions import NotFoundError, DatabaseError, StorageError
from app.domain.models.document import Document
from app.domain.models.fragment import Fragment
from app.application.services.interfaces.ingestion_service_interface import IngestionServiceInterface
from app.infrastructure.persistence.repositories.interfaces.document_repository_interface import DocumentRepositoryInterface
from app.infrastructure.persistence.repositories.interfaces.fragment_repository_interface import FragmentRepositoryInterface
from app.infrastructure.persistence.storages.interfaces.document_storage_service_interface import DocumentStorageServiceInterface


logger = logging.getLogger(__name__)


class IngestionService(IngestionServiceInterface):
    def __init__(
        self,
        document_repository: DocumentRepositoryInterface,
        fragment_repository: FragmentRepositoryInterface,
        document_storage_service: DocumentStorageServiceInterface,
    ):
        self.document_repository = document_repository
        self.fragment_repository = fragment_repository
        self.document_storage_service = document_storage_service
        self.reader_factory = ReaderFactory()
        self.cleaner_factory = TextCleanerFactory()
        self.splitter_factory = TextSplitterFactory()

    def process_document(
        self,
        document_id: int,
        db: Session,
        cleaner_type: str = "basic",
        splitter_type: str = "recursive",
        split_size: int = 500,
        split_overlap: int = 50,
        download_dir: Optional[Path] = None,
    ) -> None:
        document: Optional[Document] = self.document_repository.get_by_id(document_id, db)
        if document is None:
            logger.warning("Document not found", extra={"document_id": document_id})
            raise NotFoundError("Document not found")

        if not document.path:
            logger.error("Document has no storage path", extra={"document_id": document_id})
            raise DatabaseError("Document has no storage path")

        try:
            binary_stream: BinaryIO = self.document_storage_service.download_document(document.path)
            logger.debug("Document stream downloaded", extra={"document_id": document_id})
        except StorageError as e:
            logger.exception("Failed to download document")
            raise

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            local_file_path = temp_dir / Path(document.path).name
            try:
                with open(local_file_path, "wb") as f:
                    f.write(binary_stream.read())

                logger.info(
                    "Document saved temporarily",
                    extra={"document_id": document_id, "path": str(local_file_path)},
                )
            except Exception as e:
                logger.exception("Failed to save downloaded document temporarily")
                raise StorageError("Failed to save downloaded document locally") from e

            try:
                reader = self.reader_factory.get_reader(local_file_path)
                raw_text = reader.read(local_file_path)
            except Exception as e:
                logger.exception("Failed to read document")
                raise DatabaseError("Failed to read document") from e

            cleaner = self.cleaner_factory.get_cleaner(cleaner_type)
            clean_text = cleaner.clean_text(raw_text)

            splitter = self.splitter_factory.get_splitter(splitter_type)
            splits = splitter.split_text(clean_text, size=split_size, overlap=split_overlap)

            for idx, content in enumerate(splits):
                fragment = Fragment(
                    document_id=document.id,
                    content=content,
                    fragment_index=idx,
                    chunk_size=split_size,
                    created_by=document.created_by,
                    created_at=datetime.now(),
                )
                self.fragment_repository.create(fragment, db)
                logger.debug(
                    "Persisted fragment",
                    extra={"document_id": document_id, "fragment_index": idx},
                )

        logger.info(
            "Document ingested successfully",
            extra={"document_id": document_id, "fragment_count": len(splits)},
        )
