import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.services.document_ingestion_service.exceptions.document_ingestion_service_exception import (
    DocumentIngestionCleanException,
    DocumentIngestionEmbedException,
    DocumentIngestionPersistenceException,
    DocumentIngestionReadException,
    DocumentIngestionServiceException,
    DocumentIngestionSplitException
)
from app.application.services.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface
)
from app.application.services.document_ingestion_service.document_ingestion_service_settings import (
    DocumentIngestionServiceSettings
)
from app.domain.constants.document_status import DocumentStatus
from app.domain.models.document import Document
from app.domain.models.fragment import Fragment
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface
)
from app.infrastructure.persistence.database.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.interfaces.fragment_repository_interface import (
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
            database_manager: DatabaseManagerInterface,
            document_ingestion_service_settings: Optional[DocumentIngestionServiceSettings] = None
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._reader_factory = reader_factory
        self._cleaner_factory = text_cleaner_factory
        self._splitter_factory = text_splitter_factory
        self._embedder_factory = embedder_factory
        self._database_manager = database_manager
        self._document_ingestion_service_settings = document_ingestion_service_settings or DocumentIngestionServiceSettings()

    async def process_document(
            self,
            document: Document,
            local_file_path: Path
    ) -> None:
        logger.info(
            "Document ingestion initiated",
            extra={
                "document_id": document.id,
                "file_path": str(local_file_path)
            }
        )

        try:
            raw_text = await self._read_document(document, local_file_path)
            clean_text = await self._clean_text(document, raw_text)
            chunks = await self._split_text(document, clean_text)
            embeddings = await self._embed_chunks(document, chunks)
            fragments = self._build_fragments(document, chunks, embeddings)

            await self._persist_fragments_and_update_document(document, fragments)

            logger.info(
                "Document ingestion completed",
                extra={
                    "document_id": document.id,
                    "fragment_count": len(fragments)
                }
            )

        except (
                DocumentIngestionReadException,
                DocumentIngestionCleanException,
                DocumentIngestionSplitException,
                DocumentIngestionEmbedException,
                DocumentIngestionPersistenceException
        ):
            await self._mark_document_as_failed(document)
            raise

        except Exception as e:
            await self._mark_document_as_failed(document)
            logger.exception(
                "Unexpected error during document ingestion",
                extra={
                    "document_id": document.id
                }
            )
            raise DocumentIngestionServiceException(f"Document ingestion failed for document {document.id}") from e

        finally:
            await self._cleanup_temp_file(local_file_path)

    async def _read_document(
            self,
            document: Document,
            local_file_path: Path
    ) -> str:
        try:
            reader = self._reader_factory.get_reader(file_path=local_file_path)
            raw_text: str = await asyncio.to_thread(reader.read, local_file_path)

            logger.info(
                "Document read completed",
                extra={
                    "document_id": document.id,
                    "content_length": len(raw_text) if raw_text else 0
                }
            )
            return raw_text

        except Exception as e:
            raise DocumentIngestionReadException(f"Failed to read document {document.id}: {e}") from e

    async def _clean_text(
            self,
            document: Document,
            raw_text: str
    ) -> str:
        try:
            cleaner = self._cleaner_factory.get_text_cleaner(
                text_cleaner_type=self._document_ingestion_service_settings.text_cleaner_type
            )
            clean_text: str = await asyncio.to_thread(cleaner.clean_text, raw_text)

            logger.debug(
                "Text cleaning completed",
                extra={
                    "document_id": document.id
                }
            )
            return clean_text

        except Exception as e:
            raise DocumentIngestionCleanException(f"Failed to clean text for document {document.id}: {e}") from e

    async def _split_text(
            self,
            document: Document,
            clean_text: str
    ) -> List[str]:
        try:
            splitter = self._splitter_factory.get_text_splitter(
                text_splitter_type=self._document_ingestion_service_settings.text_splitter_type
            )
            chunks: List[str] = await asyncio.to_thread(splitter.split_text, clean_text)

            logger.info(
                "Text splitting completed",
                extra={
                    "document_id": document.id,
                    "chunk_count": len(chunks)
                }
            )
            return chunks

        except Exception as e:
            raise DocumentIngestionSplitException(f"Failed to split text for document {document.id}: {e}") from e

    async def _embed_chunks(
            self,
            document: Document,
            chunks: List[str],
    ) -> List[list[float]]:
        try:
            embedder = self._embedder_factory.get_embedder(
                embedder_type=self._document_ingestion_service_settings.embedder_type
            )

            all_embeddings: List[list[float]] = []
            batch_size = self._document_ingestion_service_settings.batch_size
            total_batches = (len(chunks) + batch_size - 1) // batch_size

            for batch_idx, start in enumerate(range(0, len(chunks), batch_size)):
                batch = chunks[start: start + batch_size]
                batch_embeddings: List[list[float]] = await asyncio.to_thread(
                    embedder.embed_documents, batch
                )
                all_embeddings.extend(batch_embeddings)

                logger.debug(
                    "Embedding batch completed",
                    extra={
                        "document_id": document.id,
                        "batch": f"{batch_idx + 1}/{total_batches}",
                        "batch_size": len(batch)
                    }
                )

            logger.info(
                "Embedding generation completed",
                extra={
                    "document_id": document.id,
                    "embedding_count": len(all_embeddings),
                    "batch_count": total_batches
                }
            )
            return all_embeddings

        except Exception as e:
            raise DocumentIngestionEmbedException(
                f"Failed to generate embeddings for document {document.id}: {e}"
            ) from e

    def _build_fragments(
            self,
            document: Document,
            chunks: List[str],
            embeddings: List[list[float]]
    ) -> List[Fragment]:
        now = datetime.now(timezone.utc)
        fragments = [
            Fragment(
                document_id=document.id,
                vector=embedding,
                content=chunk,
                fragment_index=idx,
                created_by=document.created_by,
                created_at=now
            )
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]

        logger.debug(
            "Fragments built",
            extra={
                "document_id": document.id,
                "fragment_count": len(fragments)
            }
        )
        return fragments

    async def _persist_fragments_and_update_document(
            self,
            document: Document,
            fragments: List[Fragment]
    ) -> None:
        try:
            async with self._database_manager.session() as database_session:
                await self._fragment_repository.create_fragments(
                    fragments=fragments,
                    database_session=database_session
                )

                document.text_cleaner_type = self._document_ingestion_service_settings.text_cleaner_type
                document.text_splitter_type = self._document_ingestion_service_settings.text_splitter_type
                document.embedder_type = self._document_ingestion_service_settings.embedder_type
                document.status = DocumentStatus.processed
                document.processing_finished_at = datetime.now(timezone.utc)

                await self._document_repository.update_document(
                    document=document,
                    database_session=database_session
                )

                logger.info(
                    "Fragments and document status persisted",
                    extra={
                        "document_id": document.id,
                        "fragment_count": len(fragments)
                    }
                )

        except Exception as e:
            raise DocumentIngestionPersistenceException(
                f"Failed to persist fragments for document {document.id}: {e}"
            ) from e

    async def _mark_document_as_failed(
            self,
            document: Document
    ) -> None:
        try:
            async with self._database_manager.session() as database_session:
                db_document = await self._document_repository.get_document_by_id(
                    document_id=document.id,
                    database_session=database_session
                )

                if db_document is not None:
                    db_document.status = DocumentStatus.failed
                    await self._document_repository.update_document(
                        document=db_document,
                        database_session=database_session
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
            if await asyncio.to_thread(file_path.exists):
                await asyncio.to_thread(file_path.unlink)
                logger.debug(
                    "Temporary file deleted",
                    extra={
                        "path": str(file_path)
                    }
                )
        except Exception as e:
            logger.warning(
                "Failed to delete temporary file",
                extra={
                    "path": str(file_path),
                    "error": str(e)
                }
            )
