import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, Request, status

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.services.document.document_ingestion_service.document_ingestion_service_settings import (
    DocumentIngestionServiceSettings
)
from app.application.services.document.document_ingestion_service.exceptions.document_ingestion_service_exception import (
    DocumentIngestionServiceCleanException,
    DocumentIngestionServiceEmbedException,
    DocumentIngestionServicePersistenceException,
    DocumentIngestionServiceReadException,
    DocumentIngestionServiceException,
    DocumentIngestionServiceSplitException
)
from app.application.services.document.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface
)
from app.domain.constants.document.document_status import DocumentStatus
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
    _PIPELINE_EXCEPTIONS = (
        DocumentIngestionServiceReadException,
        DocumentIngestionServiceCleanException,
        DocumentIngestionServiceSplitException,
        DocumentIngestionServiceEmbedException,
        DocumentIngestionServicePersistenceException,
    )

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
        self._settings = document_ingestion_service_settings or DocumentIngestionServiceSettings()

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
                "Document ingestion completed successfully",
                extra={
                    "document_id": document.id,
                    "fragment_count": len(fragments)
                }
            )

        except self._PIPELINE_EXCEPTIONS:
            await self._mark_document_as_failed(document)
            raise

        except Exception as e:
            await self._mark_document_as_failed(document)
            logger.exception(
                "Unexpected error during document_controllers ingestion",
                extra={"document_id": document.id}
            )
            raise DocumentIngestionServiceException(
                f"Document ingestion failed for document_controllers {document.id}: {e}"
            ) from e

        finally:
            await self._cleanup_temp_file(local_file_path)

    async def _read_document(self, document: Document, local_file_path: Path) -> str:
        try:
            reader = self._reader_factory.get_reader(file_path=local_file_path)

            import asyncio
            raw_text: str = await asyncio.to_thread(reader.read, local_file_path)

            if not raw_text or not raw_text.strip():
                raise DocumentIngestionServiceReadException(
                    f"Document {document.id} produced empty text after reading."
                )

            if len(raw_text) > self._settings.max_raw_text_length:
                raise DocumentIngestionServiceReadException(
                    f"Document {document.id} raw text ({len(raw_text)} chars) exceeds "
                    f"the maximum allowed ({self._settings.max_raw_text_length})."
                )

            logger.info(
                "Document read completed",
                extra={
                    "document_id": document.id,
                    "content_length": len(raw_text)
                }
            )
            return raw_text

        except DocumentIngestionServiceReadException:
            raise
        except Exception as e:
            raise DocumentIngestionServiceReadException(
                f"Failed to read document_controllers {document.id}: {e}"
            ) from e

    async def _clean_text(self, document: Document, raw_text: str) -> str:
        try:
            import asyncio
            cleaner = self._cleaner_factory.cleaner
            clean_text: str = await asyncio.to_thread(cleaner.clean_text, raw_text)

            if not clean_text or not clean_text.strip():
                raise DocumentIngestionServiceCleanException(
                    f"Document {document.id} produced empty text after cleaning."
                )

            logger.info(
                "Text cleaning completed",
                extra={
                    "document_id": document.id,
                    "input_length": len(raw_text),
                    "output_length": len(clean_text)
                }
            )
            return clean_text

        except DocumentIngestionServiceCleanException:
            raise
        except Exception as e:
            raise DocumentIngestionServiceCleanException(
                f"Failed to clean text for document_controllers {document.id}: {e}"
            ) from e

    async def _split_text(self, document: Document, clean_text: str) -> list[str]:
        try:
            import asyncio
            splitter = self._splitter_factory.splitter
            chunks: list[str] = await asyncio.to_thread(splitter.split_text, clean_text)

            if len(chunks) < self._settings.min_chunks_required:
                raise DocumentIngestionServiceSplitException(
                    f"Document {document.id} produced {len(chunks)} chunk(s), "
                    f"minimum required is {self._settings.min_chunks_required}."
                )

            logger.info(
                "Text splitting completed",
                extra={
                    "document_id": document.id,
                    "chunk_count": len(chunks)
                }
            )
            return chunks

        except DocumentIngestionServiceSplitException:
            raise
        except Exception as e:
            raise DocumentIngestionServiceSplitException(
                f"Failed to split text for document_controllers {document.id}: {e}"
            ) from e

    async def _embed_chunks(self, document: Document, chunks: list[str]) -> list[list[float]]:
        try:
            embedder = self._embedder_factory.embedder
            embeddings: list[list[float]] = await embedder.aembed_documents(chunks)

            if len(embeddings) != len(chunks):
                raise DocumentIngestionServiceEmbedException(
                    f"Document {document.id}: embedding count ({len(embeddings)}) "
                    f"does not match chunk count ({len(chunks)})."
                )

            logger.info(
                "Embedding generation completed",
                extra={
                    "document_id": document.id,
                    "embedding_count": len(embeddings),
                    "chunk_count": len(chunks)
                }
            )
            return embeddings

        except DocumentIngestionServiceEmbedException:
            raise
        except Exception as e:
            raise DocumentIngestionServiceEmbedException(
                f"Failed to generate embeddings for document_controllers {document.id}: {e}"
            ) from e

    def _build_fragments(
            self,
            document: Document,
            chunks: list[str],
            embeddings: list[list[float]]
    ) -> list[Fragment]:
        now = datetime.now(timezone.utc)

        fragments = [
            Fragment(
                document_id=document.id,
                content=chunk,
                vector=embedding,
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
            fragments: list[Fragment],
    ) -> None:
        try:
            async with self._database_manager.session() as database_session:
                await self._fragment_repository.create_fragments(
                    fragments=fragments,
                    database_session=database_session
                )

                document.text_cleaner_type = self._cleaner_factory.get_active_type().value
                document.text_splitter_type = self._splitter_factory.get_active_type().value
                document.embedder_type = self._embedder_factory.get_active_type().value
                document.status = DocumentStatus.processed
                document.processing_finished_at = datetime.now(timezone.utc)

                await self._document_repository.update_document(
                    document=document,
                    database_session=database_session,
                )

            logger.info(
                "Fragments and document_controllers status persisted",
                extra={
                    "document_id": document.id,
                    "fragment_count": len(fragments),
                    "cleaner_type": document.text_cleaner_type,
                    "splitter_type": document.text_splitter_type,
                    "embedder_type": document.embedder_type
                }
            )

        except Exception as e:
            raise DocumentIngestionServicePersistenceException(
                f"Failed to persist fragments for document_controllers {document.id}: {e}"
            ) from e

    async def _mark_document_as_failed(self, document: Document) -> None:
        try:
            async with self._database_manager.session() as database_session:
                db_document = await self._document_repository.get_document_by_id(
                    document_id=document.id,
                    database_session=database_session
                )

                if db_document is not None:
                    db_document.status = DocumentStatus.failed
                    db_document.processing_finished_at = datetime.now(timezone.utc)
                    await self._document_repository.update_document(
                        document=db_document,
                        database_session=database_session
                    )

            logger.info("Document marked as failed", extra={"document_id": document.id})

        except Exception as e:
            logger.error(
                "Failed to mark document_controllers as failed",
                extra={"document_id": document.id, "error": str(e)}
            )

    async def _cleanup_temp_file(self, file_path: Path) -> None:
        try:
            import asyncio
            if await asyncio.to_thread(file_path.exists):
                await asyncio.to_thread(file_path.unlink)
                logger.debug("Temporary file deleted", extra={"path": str(file_path)})
        except Exception as e:
            logger.warning(
                "Failed to delete temporary file",
                extra={"path": str(file_path), "error": str(e)}
            )


async def get_document_ingestion_service(request: Request) -> DocumentIngestionServiceInterface:
    try:
        return request.app.state.ingestion_pipeline
    except AttributeError:
        logger.error("DocumentIngestionService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentIngestionService is not available"
        )
