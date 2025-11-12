import logging
import os
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session

from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.exceptions.exceptions import DatabaseError
from app.domain.models.document import Document
from app.domain.models.fragment import Fragment
from app.infrastructure.persistence.repositories.document_repository import DocumentRepository
from app.infrastructure.persistence.repositories.fragment_repository import FragmentRepository

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self,
                 document_repository: DocumentRepository,
                 fragment_repository: FragmentRepository):
        self.document_repository = document_repository
        self.fragment_repository = fragment_repository
        self.reader_factory = ReaderFactory()
        self.cleaner_factory = TextCleanerFactory()
        self.splitter_factory = TextSplitterFactory()

    def process_document(
        self,
        document: Document,
        db: Session,
        local_file_path: Path,
        cleaner_type: str = "basic",
        splitter_type: str = "recursive",
        split_size: int = 500,
        split_overlap: int = 50,
    ) -> None:
        try:
            logger.info(f"Iniciando proceso de ingesta para documento {document.id}")
            reader = self.reader_factory.get_reader(local_file_path)
            raw_text = reader.read(local_file_path)

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

            logger.info(
                f"Documento {document.id} procesado con éxito con {len(splits)} fragmentos."
            )

        except Exception as e:
            logger.exception(f"Error procesando documento {document.id}")
            raise DatabaseError("Error en la ingesta del documento") from e

        finally:
            # Limpieza del archivo temporal
            try:
                if os.path.exists(local_file_path):
                    os.remove(local_file_path)
                    logger.info(f"Archivo temporal eliminado: {local_file_path}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar el archivo temporal {local_file_path}: {e}")
