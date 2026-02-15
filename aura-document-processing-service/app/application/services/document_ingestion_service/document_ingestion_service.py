import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.services.document_ingestion_service.document_ingestion_service_settings import (
    DocumentIngestionServiceSettings
)
from app.application.services.document_ingestion_service.exceptions.document_ingestion_service_exception import (
    DocumentReadException,
    DocumentCleanException,
    DocumentSplitException,
    DocumentEmbedException,
    DocumentPersistenceException,
    DocumentIngestionServiceException
)
from app.application.services.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface,
)
from app.domain.constants.document_status import DocumentStatus
from app.domain.models.document import Document
from app.domain.models.fragment import Fragment
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import \
    DatabaseManagerInterface
from app.infrastructure.persistence.database.repositories.document_repository.document_repository import (
    DocumentRepositoryInterface,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface,
)
from app.infrastructure.persistence.database.database_manager.database_manager import DatabaseManager

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
            database_manager: DatabaseManagerInterface,
            document_ingestion_service_settings: DocumentIngestionServiceSettings
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._reader_factory = reader_factory
        self._cleaner_factory = text_cleaner_factory
        self._splitter_factory = text_splitter_factory
        self._embedder_factory = embedder_factory
        self._database_manager = database_manager
        self._document_ingestion_service_settings = document_ingestion_service_settings

        self._documents_processed = 0
        self._documents_failed = 0
        self._read_errors = 0
        self._clean_errors = 0
        self._split_errors = 0
        self._embed_errors = 0
        self._persistence_errors = 0
        self._total_fragments_created = 0
        self._total_processing_time = 0.0
        self._last_health_check: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
            cls,
            document_repository: DocumentRepositoryInterface,
            fragment_repository: FragmentRepositoryInterface,
            reader_factory: ReaderFactory,
            text_cleaner_factory: TextCleanerFactory,
            text_splitter_factory: TextSplitterFactory,
            embedder_factory: EmbedderFactory,
            database_manager: DatabaseManager,
            text_cleaner_type: Optional[str] = None,
            text_splitter_type: Optional[str] = None,
            embedder_type: Optional[str] = None,
            split_size: Optional[int] = None,
            split_overlap: Optional[int] = None,
            **config_kwargs
    ) -> "DocumentIngestionService":
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

        document_ingestion_service_settings = DocumentIngestionServiceSettings(
            **config_kwargs
        )

        return cls(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            reader_factory=reader_factory,
            text_cleaner_factory=text_cleaner_factory,
            text_splitter_factory=text_splitter_factory,
            embedder_factory=embedder_factory,
            database_manager=database_manager,
            document_ingestion_service_settings=document_ingestion_service_settings
        )

    async def process_document(
            self,
            document: Document,
            local_file_path: Path
    ) -> None:
        start_time = time.time()

        logger.info(
            "Starting document processing",
            extra={
                "document_id": document.id,
                "file_path": str(local_file_path),
                "status": document.status
            }
        )

        try:
            loop = asyncio.get_running_loop()

            try:
                reader = self._reader_factory.get_reader(
                    file_path=local_file_path
                )
                reader_result = await loop.run_in_executor(
                    None,
                    reader.read,
                    local_file_path
                )

                logger.info(
                    "Document read successfully",
                    extra={
                        "document_id": document.id,
                        "content_length": len(reader_result) if reader_result else 0
                    }
                )

            except Exception as e:
                self._read_errors += 1
                logger.error(
                    "Failed to read document",
                    extra={
                        "document_id": document.id,
                        "error": str(e)
                    }
                )
                raise DocumentReadException(f"Failed to read document: {str(e)}") from e

            try:
                cleaner = self._cleaner_factory.get_text_cleaner(
                    method=self._document_ingestion_service_settings.text_cleaner_type
                )
                clean_result = await loop.run_in_executor(
                    None,
                    cleaner.clean_text,
                    reader_result
                )

                logger.debug(
                    "Text cleaned successfully",
                    extra={
                        "document_id": document.id
                    }
                )

            except Exception as e:
                self._clean_errors += 1
                logger.error(
                    "Failed to clean text",
                    extra={
                        "document_id": document.id,
                        "error": str(e)
                    }
                )
                raise DocumentCleanException(f"Failed to clean text: {str(e)}") from e

            try:
                splitter = self._splitter_factory.get_text_splitter(
                    method=self._document_ingestion_service_settings.text_splitter_type
                )
                splitter_result = await loop.run_in_executor(
                    None,
                    lambda: splitter.split_text(
                        text=clean_result,
                        size=self._document_ingestion_service_settings.split_size,
                        overlap=self._document_ingestion_service_settings.split_overlap
                    )
                )

                logger.info(
                    "Text split successfully",
                    extra={
                        "document_id": document.id,
                        "num_chunks": len(splitter_result)
                    }
                )

            except Exception as e:
                self._split_errors += 1
                logger.error(
                    "Failed to split text",
                    extra={
                        "document_id": document.id,
                        "error": str(e)
                    }
                )
                raise DocumentSplitException(f"Failed to split text: {str(e)}") from e

            try:
                embedder = self._embedder_factory.get_embedder(
                    method=self._document_ingestion_service_settings.embedder_type
                )
                embedder_result = await loop.run_in_executor(
                    None,
                    embedder.embed_documents,
                    splitter_result
                )

                logger.info(
                    "Embeddings generated successfully",
                    extra={
                        "document_id": document.id,
                        "num_embeddings": len(embedder_result)
                    }
                )

            except Exception as e:
                self._embed_errors += 1
                logger.error(
                    "Failed to generate embeddings",
                    extra={
                        "document_id": document.id,
                        "error": str(e)
                    }
                )
                raise DocumentEmbedException(f"Failed to generate embeddings: {str(e)}") from e

            fragments = self._create_fragments(
                document=document,
                embeddings=embedder_result,
                chunks=splitter_result
            )

            try:
                await self._persist_fragments_and_update_document(
                    document=document,
                    fragments=fragments
                )

                self._total_fragments_created += len(fragments)

                logger.info(
                    "Document processing completed successfully",
                    extra={
                        "document_id": document.id,
                        "num_fragments": len(fragments)
                    }
                )

            except Exception as e:
                self._persistence_errors += 1
                logger.error(
                    "Failed to persist fragments",
                    extra={
                        "document_id": document.id,
                        "error": str(e)
                    }
                )
                raise DocumentPersistenceException(f"Failed to persist fragments: {str(e)}") from e

            self._documents_processed += 1
            elapsed = time.time() - start_time
            self._total_processing_time += elapsed

            logger.info(
                "Document processing metrics",
                extra={
                    "document_id": document.id,
                    "elapsed_seconds": round(elapsed, 2),
                    "fragments_created": len(fragments)
                }
            )

        except (
                DocumentReadException,
                DocumentCleanException,
                DocumentSplitException,
                DocumentEmbedException,
                DocumentPersistenceException
        ):
            self._documents_failed += 1
            await self._mark_document_as_failed(document)
            raise

        except Exception as e:
            self._documents_failed += 1
            logger.exception(
                "Unexpected error processing document",
                extra={
                    "document_id": document.id
                }
            )
            await self._mark_document_as_failed(document)
            raise DocumentIngestionServiceException(f"Document processing failed: {str(e)}") from e

        finally:
            if self._document_ingestion_service_settings.cleanup_temp_files:
                await self._cleanup_temp_file(local_file_path)

    def _create_fragments(
            self,
            document: Document,
            embeddings: List,
            chunks: List[str]
    ) -> List[Fragment]:
        fragments = []

        for idx in range(len(embeddings)):
            fragments.append(
                Fragment(
                    document_id=document.id,
                    vector=embeddings[idx],
                    content=chunks[idx],
                    fragment_index=idx,
                    created_by=document.created_by,
                    created_at=datetime.utcnow(),
                )
            )

        logger.debug(
            "Fragments created",
            extra={
                "document_id": document.id,
                "num_fragments": len(fragments)
            }
        )

        return fragments

    async def _persist_fragments_and_update_document(
            self,
            document: Document,
            fragments: List[Fragment]
    ) -> None:
        async with self._database_manager.session() as database_session:
            await self._fragment_repository.create_fragments(
                fragments=fragments,
                database_session=database_session,
            )

            document.text_cleaner_type = self._document_ingestion_service_settings.text_cleaner_type
            document.text_splitter_type = self._document_ingestion_service_settings.text_splitter_type
            document.embedder_type = self._document_ingestion_service_settings.embedder_type
            document.split_size = self._document_ingestion_service_settings.split_size
            document.split_overlap = self._document_ingestion_service_settings.split_overlap
            document.status = DocumentStatus.done

            await self._document_repository.update_document(
                document=document,
                database_session=database_session,
            )

    async def _mark_document_as_failed(
            self,
            document: Document
    ) -> None:
        try:
            async with self._database_manager.session() as database_session:
                db_document = await self._document_repository.get_document_by_id(
                    document.id,
                    database_session
                )

                if db_document:
                    db_document.status = DocumentStatus.failed
                    await self._document_repository.update_document(
                        document=db_document,
                        database_session=database_session,
                    )

                    logger.info(
                        "Document marked as failed",
                        extra={
                            "document_id": document.id
                        }
                    )

        except Exception as e:
            logger.error(
                "Failed to mark document as failed",
                extra={
                    "document_id": document.id,
                    "error": str(e)
                }
            )

    async def _cleanup_temp_file(
            self,
            file_path: Path
    ) -> None:
        try:
            if file_path.exists():
                await asyncio.to_thread(file_path.unlink)
                logger.debug(
                    "Temporary file deleted",
                    extra={
                        "path": str(file_path)
                    }
                )
        except Exception as e:
            logger.warning(
                "Could not delete temporary file",
                extra={
                    "path": str(file_path),
                    "error": str(e)
                }
            )

    def get_metrics(
            self
    ) -> Dict[str, int]:
        return {
            "documents_processed": self._documents_processed,
            "documents_failed": self._documents_failed,
            "read_errors": self._read_errors,
            "clean_errors": self._clean_errors,
            "split_errors": self._split_errors,
            "embed_errors": self._embed_errors,
            "persistence_errors": self._persistence_errors,
            "total_fragments_created": self._total_fragments_created,
        }
