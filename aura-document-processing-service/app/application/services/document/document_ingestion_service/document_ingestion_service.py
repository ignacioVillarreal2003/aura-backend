import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from fastapi import HTTPException, Request, status
import asyncio

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
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.orm.fragment import Fragment
from app.infrastructure.persistence.database.database_manager.database_manager_interface import (
    DatabaseManagerInterface
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository_interface import (
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
        self._settings = document_ingestion_service_settings or DocumentIngestionServiceSettings()

    async def process_document(
            self,
            document: Document,
            local_file_path: Path,
            prefer_docling: bool = False
    ) -> None:
        logger.info(
            "Document ingestion was initiated.",
            extra={
                "document_id": document.id,
                "file_name": local_file_path.name,
                "prefer_docling": prefer_docling
            }
        )

        try:
            raw_text = await self._read_document(
                document,
                local_file_path,
                prefer_docling=prefer_docling
            )
            clean_text = await self._clean_text(document, raw_text)
            chunks = await self._split_text(document, clean_text)
            embeddings = await self._embed_chunks(document, chunks)
            fragments = self._build_fragments(document, chunks, embeddings)
            await self._persist_fragments_and_update_document(document, fragments)

            logger.info(
                "Document ingestion completed successfully.",
                extra={
                    "document_id": document.id,
                    "fragment_count": len(fragments)
                }
            )

        except (
                DocumentIngestionServiceReadException,
                DocumentIngestionServiceCleanException,
                DocumentIngestionServiceSplitException,
                DocumentIngestionServiceEmbedException,
                DocumentIngestionServicePersistenceException,
        ):
            await self._mark_document_as_failed(document)
            raise

        except Exception as e:
            await self._mark_document_as_failed(document)
            logger.exception(
                "An unexpected error occurred during document ingestion.",
                extra={
                    "document_id": document.id
                }
            )
            raise DocumentIngestionServiceException("Document ingestion failed.") from e

        finally:
            await self._cleanup_temp_file(local_file_path)

    async def _read_document(
            self,
            document: Document,
            local_file_path: Path,
            *,
            prefer_docling: bool = False,
    ) -> str:
        try:
            reader = self._reader_factory.get_reader(
                local_file_path,
                prefer_docling=prefer_docling
            )

            raw_text: str = await asyncio.to_thread(reader.read, local_file_path)

            if not raw_text or not raw_text.strip():
                raise DocumentIngestionServiceReadException("The document produced no text after reading.")

            if len(raw_text) > self._settings.max_raw_text_length:
                raise DocumentIngestionServiceReadException("The extracted text exceeds the maximum allowed length.")

            logger.info(
                "The document was read successfully.",
                extra={
                    "document_id": document.id,
                    "content_length": len(raw_text)
                }
            )
            return raw_text

        except DocumentIngestionServiceReadException:
            raise
        except Exception as e:
            raise DocumentIngestionServiceReadException("Failed to read the document.") from e

    async def _clean_text(
            self,
            document: Document,
            raw_text: str
    ) -> str:
        try:
            cleaner = self._cleaner_factory.cleaner
            clean_text: str = await asyncio.to_thread(cleaner.clean_text, raw_text)

            if not clean_text or not clean_text.strip():
                raise DocumentIngestionServiceCleanException("The document produced no text after cleaning.")

            logger.info(
                "Text cleaning completed.",
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
            raise DocumentIngestionServiceCleanException("Failed to clean the document text.") from e

    async def _split_text(
            self,
            document: Document,
            clean_text: str
    ) -> list[str]:
        try:
            import asyncio
            splitter = self._splitter_factory.splitter
            chunks: list[str] = await asyncio.to_thread(splitter.split_text, clean_text)

            if len(chunks) < self._settings.min_chunks_required:
                raise DocumentIngestionServiceSplitException("The document did not produce enough text segments.")

            logger.info(
                "Text splitting completed.",
                extra={
                    "document_id": document.id,
                    "chunk_count": len(chunks)
                }
            )
            return chunks

        except DocumentIngestionServiceSplitException:
            raise
        except Exception as e:
            raise DocumentIngestionServiceSplitException("Failed to split the document text.") from e

    async def _embed_chunks(
            self,
            document: Document,
            chunks: list[str]
    ) -> list[list[float]]:
        try:
            embedder = self._embedder_factory.embedder
            embeddings: list[list[float]] = await embedder.aembed_documents(chunks)

            if len(embeddings) != len(chunks):
                raise DocumentIngestionServiceEmbedException(
                    "The number of embeddings does not match the number of text segments."
                )

            logger.info(
                "Embedding generation completed.",
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
            raise DocumentIngestionServiceEmbedException("Failed to generate embeddings for the document.") from e

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
            "Fragments were built from the document chunks.",
            extra={
                "document_id": document.id,
                "fragment_count": len(fragments)
            }
        )
        return fragments

    async def _persist_fragments_and_update_document(
            self,
            document: Document,
            fragments: list[Fragment]
    ) -> None:
        try:
            async def _operation(database_session):
                await self._fragment_repository.create_fragments(
                    fragments=fragments,
                    database_session=database_session
                )

                document.text_cleaner_type = self._cleaner_factory.get_active_type().value
                document.text_splitter_type = self._splitter_factory.get_active_type().value
                document.embedder_type = self._embedder_factory.get_active_type().value
                current_status = (
                    document.status
                    if isinstance(document.status, DocumentStatus)
                    else DocumentStatus(document.status)
                )
                current_status.transition_to(DocumentStatus.processed)
                document.status = DocumentStatus.processed
                document.processing_finished_at = datetime.now(timezone.utc)

                await self._document_repository.update_document(
                    document=document,
                    database_session=database_session,
                )
            await self._database_manager.run_write_transaction_with_retry(
                _operation,
                operation_name="document_ingestion.persist_fragments_and_update_document",
            )

            logger.info(
                "Fragments and document status were saved.",
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
                "Failed to save fragments or update the document."
            ) from e

    async def _mark_document_as_failed(
            self,
            document: Document
    ) -> None:
        try:
            async def _operation(database_session):
                db_document = await self._document_repository.get_document_by_id(
                    document_id=document.id,
                    database_session=database_session
                )

                if db_document is not None:
                    st = (
                        db_document.status
                        if isinstance(db_document.status, DocumentStatus)
                        else DocumentStatus(db_document.status)
                    )
                    st.transition_to(DocumentStatus.failed)
                    db_document.status = DocumentStatus.failed
                    db_document.processing_finished_at = datetime.now(timezone.utc)
                    await self._document_repository.update_document(
                        document=db_document,
                        database_session=database_session
                    )
            await self._database_manager.run_write_transaction_with_retry(
                _operation,
                operation_name="document_ingestion.mark_document_as_failed",
            )

            logger.info(
                "The document was marked as failed.",
                extra={
                    "document_id": document.id
                }
            )

        except Exception as e:
            logger.error(
                "Failed to mark the document as failed.",
                extra={
                    "document_id": document.id,
                    "exception_type": type(e).__name__
                }
            )

    @staticmethod
    async def _cleanup_temp_file(
            file_path: Path
    ) -> None:
        try:
            import asyncio
            if await asyncio.to_thread(file_path.exists):
                await asyncio.to_thread(file_path.unlink)
                logger.debug(
                    "The temporary file was deleted.",
                    extra={
                        "path": str(file_path)
                    }
                )
        except Exception as e:
            logger.warning(
                "Failed to delete the temporary file.",
                extra={
                    "path": str(file_path),
                    "exception_type": type(e).__name__
                }
            )

async def get_document_ingestion_service(
        request: Request
) -> DocumentIngestionServiceInterface:
    try:
        return request.app.state.document_ingestion_service
    except AttributeError:
        logger.error("DocumentIngestionService is not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DocumentIngestionService is not registered on the application state."
        )

