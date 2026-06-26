import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.constants.text_splitter_type import TextSplitterType
from app.application.processors.text_splitters.dtos.document_chunk import DocumentChunk
from app.application.processors.text_splitters.exceptions.text_splitter_exception import (
    TextSplitterException,
)
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.services.document.document_ingestion_service.document_ingestion_service_settings import (
    DocumentIngestionServiceSettings,
)
from app.configuration.metrics import (
    document_fragments_per_document,
    document_ingestion_duration_seconds,
    document_ingestion_total,
    observe_stage,
    pipeline_stage_failures_total,
    structural_chunk_fallback_total,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.document_enrichment_publisher_interface import (
    DocumentEnrichmentPublisherInterface,
)
from app.application.services.document.document_ingestion_service.exceptions.document_ingestion_service_exception import (
    DocumentIngestionServiceCleanException,
    DocumentIngestionServiceEmbedException,
    DocumentIngestionServicePersistenceException,
    DocumentIngestionServiceReadException,
    DocumentIngestionServiceException,
    DocumentIngestionServiceSplitException,
)
from app.application.services.document.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface,
)
from app.domain.constants.document.document_status import DocumentStatus
from app.infrastructure.persistence.database.orm.document import Document
from app.infrastructure.persistence.database.orm.fragment import Fragment
from app.infrastructure.persistence.database.database_manager.interfaces.database_manager_interface import (
    DatabaseManagerInterface,
)
from app.infrastructure.persistence.database.repositories.interfaces.document_repository_interface import (
    DocumentRepositoryInterface,
)
from app.infrastructure.messaging.rabbitmq.publisher.interfaces.graph_extraction_publisher_interface import (
    GraphExtractionPublisherInterface,
)
from app.infrastructure.persistence.database.repositories.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _ChunkingOutcome:
    chunks: list[DocumentChunk]
    splitter_type: str
    cleaner_type: Optional[str]
    chunk_size: Optional[int]
    chunk_overlap: Optional[int]


_FAILURE_STAGE_BY_EXCEPTION: dict[type[Exception], str] = {
    DocumentIngestionServiceReadException: "read",
    DocumentIngestionServiceCleanException: "clean",
    DocumentIngestionServiceSplitException: "split",
    DocumentIngestionServiceEmbedException: "embed",
    DocumentIngestionServicePersistenceException: "persist",
}


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
            document_ingestion_service_settings: Optional[DocumentIngestionServiceSettings] = None,
            graph_extraction_publisher: Optional[GraphExtractionPublisherInterface] = None,
            document_enrichment_publisher: Optional[DocumentEnrichmentPublisherInterface] = None,
    ) -> None:
        self._document_repository = document_repository
        self._fragment_repository = fragment_repository
        self._reader_factory = reader_factory
        self._cleaner_factory = text_cleaner_factory
        self._splitter_factory = text_splitter_factory
        self._embedder_factory = embedder_factory
        self._database_manager = database_manager
        self._settings = document_ingestion_service_settings or DocumentIngestionServiceSettings()
        self._graph_extraction_publisher = graph_extraction_publisher
        self._document_enrichment_publisher = document_enrichment_publisher

    async def process_document(
            self,
            document: Document,
            local_file_path: Path,
            user: AuthenticatedUser,
            prefer_docling: bool = False,
            enrich: bool = True,
            graph_extract: bool = True,
    ) -> None:
        logger.info(
            "Document ingestion was initiated.",
            extra={
                "document_id": document.id,
                "file_name": local_file_path.name,
                "prefer_docling": prefer_docling,
                "enrich": enrich,
                "graph_extract": graph_extract,
            }
        )

        start = time.perf_counter()
        try:
            with observe_stage("chunk"):
                outcome = await self._produce_chunks(
                    document,
                    local_file_path,
                    prefer_docling=prefer_docling,
                )
            if len(outcome.chunks) > self._settings.max_chunks_per_document:
                raise DocumentIngestionServiceSplitException(
                    "The document produced too many text segments to embed safely "
                    f"({len(outcome.chunks)} > {self._settings.max_chunks_per_document})."
                )
            texts = [chunk.embed_text or chunk.text for chunk in outcome.chunks]
            with observe_stage("embed"):
                embeddings = await self._embed_chunks(document, texts)
            fragments = self._build_fragments(document, outcome.chunks, embeddings)
            with observe_stage("persist"):
                await self._persist_fragments_and_update_document(document, fragments, outcome)

            document_ingestion_total.labels(result="success").inc()
            document_fragments_per_document.observe(len(fragments))

            logger.info(
                "Document ingestion completed successfully.",
                extra={
                    "document_id": document.id,
                    "fragment_count": len(fragments),
                    "splitter_type": outcome.splitter_type,
                }
            )

            if enrich:
                await self._publish_document_enrichment_event(document, user)

            if graph_extract:
                await self._publish_graph_extraction_event(document, user)

        except (
                DocumentIngestionServiceReadException,
                DocumentIngestionServiceCleanException,
                DocumentIngestionServiceSplitException,
                DocumentIngestionServiceEmbedException,
                DocumentIngestionServicePersistenceException,
        ) as e:
            document_ingestion_total.labels(result="failure").inc()
            pipeline_stage_failures_total.labels(
                stage=_FAILURE_STAGE_BY_EXCEPTION.get(type(e), "unexpected")
            ).inc()
            await self._mark_document_as_failed(document)
            raise

        except Exception as e:
            document_ingestion_total.labels(result="failure").inc()
            pipeline_stage_failures_total.labels(stage="unexpected").inc()
            await self._mark_document_as_failed(document)
            logger.exception(
                "An unexpected error occurred during document ingestion.",
                extra={
                    "document_id": document.id
                }
            )
            raise DocumentIngestionServiceException("Document ingestion failed.") from e

        finally:
            document_ingestion_duration_seconds.observe(time.perf_counter() - start)
            await self._cleanup_temp_file(local_file_path)

    async def _produce_chunks(
            self,
            document: Document,
            local_file_path: Path,
            *,
            prefer_docling: bool,
    ) -> _ChunkingOutcome:
        if self._splitter_factory.get_active_type() == TextSplitterType.docling_hybrid:
            splitter = await asyncio.to_thread(self._splitter_factory.get_structured_splitter)
            if splitter is None:
                structural_chunk_fallback_total.labels(reason="unavailable").inc()
                logger.warning(
                    "Structural chunking is configured but unavailable; "
                    "falling back to the flat-text splitter.",
                    extra={"document_id": document.id},
                )
            elif splitter.supports(local_file_path):
                try:
                    chunks = await asyncio.to_thread(splitter.chunk_file, local_file_path)
                    chunks = [c for c in chunks if c.text and c.text.strip()]
                    if len(chunks) < self._settings.min_chunks_required:
                        raise DocumentIngestionServiceSplitException(
                            "The document did not produce enough text segments."
                        )
                    chunk_size, chunk_overlap = splitter.get_chunk_params()
                    logger.info(
                        "Structural chunking completed.",
                        extra={"document_id": document.id, "chunk_count": len(chunks)},
                    )
                    return _ChunkingOutcome(
                        chunks=chunks,
                        splitter_type=TextSplitterType.docling_hybrid.value,
                        cleaner_type=None,
                        chunk_size=chunk_size,
                        chunk_overlap=chunk_overlap,
                    )
                except TextSplitterException:
                    structural_chunk_fallback_total.labels(reason="exception").inc()
                    logger.warning(
                        "Structural chunking failed; falling back to the flat-text splitter.",
                        exc_info=True,
                        extra={"document_id": document.id},
                    )

        raw_text = await self._read_document(document, local_file_path, prefer_docling=prefer_docling)
        clean_text = await self._clean_text(document, raw_text)

        splitter = self._splitter_factory.get_classic_splitter()
        try:
            chunks = await asyncio.to_thread(splitter.split_text, clean_text)
        except DocumentIngestionServiceSplitException:
            raise
        except Exception as e:
            raise DocumentIngestionServiceSplitException("Failed to split the document text.") from e

        chunks = [c for c in chunks if c.text and c.text.strip()]
        if len(chunks) < self._settings.min_chunks_required:
            raise DocumentIngestionServiceSplitException("The document did not produce enough text segments.")

        chunk_size, chunk_overlap = splitter.get_chunk_params()
        logger.info(
            "Text splitting completed.",
            extra={"document_id": document.id, "chunk_count": len(chunks)},
        )
        return _ChunkingOutcome(
            chunks=chunks,
            splitter_type=self._splitter_factory.get_classic_type().value,
            cleaner_type=self._cleaner_factory.get_active_type().value,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    async def _read_document(
            self,
            document: Document,
            local_file_path: Path,
            *,
            prefer_docling: bool = False,
    ) -> str:
        try:
            readers = self._reader_factory.get_capable_readers(
                local_file_path,
                prefer_docling=prefer_docling,
            )
        except Exception as e:
            raise DocumentIngestionServiceReadException("Failed to read the document.") from e

        if not readers:
            raise DocumentIngestionServiceReadException("No reader is available for this document.")

        last_error: Optional[Exception] = None
        for index, reader in enumerate(readers):
            reader_name = type(reader).__name__
            try:
                raw_text: str = await asyncio.to_thread(reader.read, local_file_path)

                if not raw_text or not raw_text.strip():
                    raise DocumentIngestionServiceReadException("The document produced no text after reading.")

                if len(raw_text) > self._settings.max_raw_text_length:
                    raise DocumentIngestionServiceReadException(
                        "The extracted text exceeds the maximum allowed length."
                    )

                logger.info(
                    "The document was read successfully.",
                    extra={
                        "document_id": document.id,
                        "reader": reader_name,
                        "content_length": len(raw_text)
                    }
                )
                return raw_text

            except Exception as e:
                last_error = e
                remaining = len(readers) - index - 1
                logger.warning(
                    "A reader failed to read the document; trying the next capable reader."
                    if remaining
                    else "All capable readers failed to read the document.",
                    extra={
                        "document_id": document.id,
                        "reader": reader_name,
                        "exception_type": type(e).__name__,
                        "remaining_readers": remaining,
                    },
                )

        raise DocumentIngestionServiceReadException("Failed to read the document.") from last_error

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
            chunks: list[DocumentChunk],
            embeddings: list[list[float]]
    ) -> list[Fragment]:
        now = datetime.now(timezone.utc)

        embedding_model = self._embedder_factory.get_active_model_name()
        embedding_dim = self._embedder_factory.get_vector_dimension()
        embedding_identity = self._embedder_factory.get_active_embedding_identity()

        fragments = [
            Fragment(
                document_id=document.id,
                content=chunk.text,
                vector=embedding,
                embedding_model=embedding_model,
                embedding_dim=embedding_dim,
                embedding_identity=embedding_identity,
                fragment_index=idx,
                page_number=chunk.page_number,
                section_path=chunk.section_path,
                heading=chunk.heading,
                char_start=chunk.char_start,
                char_end=chunk.char_end,
                bbox=chunk.bbox,
                created_by=document.created_by,
                created_at=now
            )
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings, strict=True))
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
            fragments: list[Fragment],
            outcome: "_ChunkingOutcome",
    ) -> None:
        try:
            async def _operation(database_session: AsyncSession) -> None:
                await self._fragment_repository.create_fragments(
                    fragments=fragments,
                    database_session=database_session
                )

                document.text_cleaner_type = outcome.cleaner_type
                document.text_splitter_type = outcome.splitter_type
                document.embedder_type = self._embedder_factory.get_active_type().value
                document.split_size = outcome.chunk_size
                document.split_overlap = outcome.chunk_overlap
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
            async def _operation(database_session: AsyncSession) -> None:
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

    async def _publish_document_enrichment_event(
            self,
            document: Document,
            user: AuthenticatedUser,
    ) -> None:
        if self._document_enrichment_publisher is None:
            return
        try:
            await self._document_enrichment_publisher.publish(
                document_id=int(document.id),
                user=user,
            )
            logger.info(
                "A document enrichment event was enqueued.",
                extra={"document_id": document.id, "user_id": user.id},
            )
        except Exception:
            logger.warning(
                "Failed to enqueue document enrichment; document ingestion succeeded.",
                extra={"document_id": document.id, "user_id": user.id},
            )

    async def _publish_graph_extraction_event(
            self,
            document: Document,
            user: AuthenticatedUser,
    ) -> None:
        if self._graph_extraction_publisher is None:
            return
        try:
            await self._graph_extraction_publisher.publish(
                document_id=int(document.id),
                user=user,
            )
            logger.info(
                "A knowledge graph extraction event was enqueued.",
                extra={"document_id": document.id, "user_id": user.id},
            )
        except Exception:
            logger.warning(
                "Failed to enqueue knowledge graph extraction; document ingestion succeeded.",
                extra={"document_id": document.id, "user_id": user.id},
            )

    @staticmethod
    async def _cleanup_temp_file(
            file_path: Path
    ) -> None:
        try:
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
