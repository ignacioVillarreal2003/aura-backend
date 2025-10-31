from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.services.minio_service import download_document
from app.application.exceptions.exceptions import NotFoundError, DatabaseError
from app.domain.models.document_orm import DocumentORM
from app.domain.models.fragment import Fragment
from app.persistence.repositories.fragment_repository import FragmentRepository
from app.persistence.repositories.document_repository import DocumentRepository


class IngestionService:
    def __init__(self, db_url: str):
        self.reader_factory = ReaderFactory()
        self.cleaner_factory = TextCleanerFactory()
        self.splitter_factory = TextSplitterFactory()

    def process_document(
        self,
        db: Session,
        document_id: int,
        *,
        cleaner_type: str = "basic",
        splitter_type: str = "char",
        chunk_size: int = 500,
        overlap: int = 50,
        download_dir: Optional[Path] = None
    ) -> int:
        # 1) Fetch document metadata
        document: Optional[DocumentORM] = DocumentRepository.get_by_id(db, document_id)
        if document is None:
            raise NotFoundError("Document not found")
        if not document.path:
            raise DatabaseError("Document has no storage path")

        # 2) Download from MinIO to local path
        local_file_path: Path = download_document(document.path, download_dir)

        # 3) Read (OCR if needed)
        reader = self.reader_factory.get_reader(local_file_path)
        raw_text = reader.read(local_file_path)

        # 4) Clean
        cleaner = self.cleaner_factory.get_cleaner(cleaner_type)
        clean_text = cleaner.clean_text(raw_text)

        # 5) Split
        splitter = self.splitter_factory.get_splitter(splitter_type)
        chunks = splitter.split_text(clean_text, size=chunk_size, overlap=overlap)

        # 6) Persist fragments
        created_count = 0
        for idx, content in enumerate(chunks):
            fragment = Fragment(
                source_document_id=document.id,
                vector=None,
                content=content,
                fragment_index=idx,
                chunk_size=chunk_size,
                created_by=document.created_by
            )
            FragmentRepository.create(db, fragment)
            created_count += 1

        return created_count
