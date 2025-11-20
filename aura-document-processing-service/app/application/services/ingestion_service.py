import logging
import os
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.exceptions.exceptions import DatabaseError
from app.configuration.environment_variables import environment_variables
from app.domain.models.document import Document
from app.domain.models.fragment import Fragment
from app.infrastructure.persistence.repositories.interfaces.document_repository_interface import \
    DocumentRepositoryInterface
from app.infrastructure.persistence.repositories.interfaces.fragment_repository_interface import \
    FragmentRepositoryInterface

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self,
                 document_repository: DocumentRepositoryInterface,
                 fragment_repository: FragmentRepositoryInterface):
        self.document_repository = document_repository
        self.fragment_repository = fragment_repository
        self.reader_factory = ReaderFactory()
        self.cleaner_factory = TextCleanerFactory()
        self.splitter_factory = TextSplitterFactory()
        self.embedder_factory = EmbedderFactory()

    def process_document(self,
                         document: Document,
                         db: Session,
                         local_file_path: Path,
                         cleaner_type: str = environment_variables.cleaner_type,
                         splitter_type: str = environment_variables.splitter_type,
                         embedder_type: str = environment_variables.embedder_type,
                         split_size: int = environment_variables.split_size,
                         split_overlap: int = environment_variables.split_overlap) -> None:
        try:
            reader = self.reader_factory.get_reader(local_file_path)
            reader_result = reader.read(local_file_path)

            cleaner = self.cleaner_factory.get_text_cleaner(cleaner_type)
            clean_result = cleaner.clean_text(reader_result)

            splitter = self.splitter_factory.get_text_splitter(splitter_type)
            splitter_result = splitter.split_text(clean_result,
                                                  size=split_size,
                                                  overlap=split_overlap)

            embedder = self.embedder_factory.get_embedder(embedder_type)
            embedder_result = embedder.embed_documents(splitter_result)

            for idx in range(len(embedder_result)):
                fragment = Fragment(
                    document_id=document.id,
                    vector=embedder_result[idx],
                    embedding_model=embedder_type,
                    content=splitter_result[idx],
                    fragment_index=idx,
                    chunk_size=split_size,
                    created_by=document.created_by,
                    created_at=datetime.now(),
                )
                self.fragment_repository.create(fragment, db)

        except Exception as e:
            logger.exception(f"Error procesando documento {document.id}")
            raise DatabaseError("Error en la ingesta del documento") from e

        finally:
            try:
                if os.path.exists(local_file_path):
                    os.remove(local_file_path)
                    logger.info(f"Archivo temporal eliminado: {local_file_path}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar el archivo temporal {local_file_path}: {e}")
