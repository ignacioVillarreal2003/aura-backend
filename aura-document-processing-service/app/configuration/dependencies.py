import logging
from fastapi import FastAPI

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.services.document.create_document_service.create_document_service import CreateDocumentService
from app.application.services.document.delete_document_service.delete_document_service import DeleteDocumentService
from app.application.services.document.document_ingestion_service.document_ingestion_service import DocumentIngestionService
from app.application.services.document.document_query_service.document_query_service import DocumentQueryService
from app.application.services.fragment.fragment_query_service.fragment_query_service import FragmentQueryService
from app.application.services.document.post_process_document_service.post_process_document_service import (
    PostProcessDocumentService
)
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_service import (
    PostProcessFragmentService
)
from app.infrastructure.http.authentication_provider.authentication_provider import AuthenticationProvider
from app.infrastructure.http.http_client.http_client import HttpClient
from app.infrastructure.http.llm_provider.llm_provider import LlmProvider
from app.infrastructure.persistence.database.database_manager.database_manager import DatabaseManager
from app.infrastructure.persistence.database.repositories.document_repository.document_repository import DocumentRepository
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository import FragmentRepository
from app.infrastructure.persistence.storages.document_storage.document_storage import DocumentStorage
from app.infrastructure.persistence.storages.minio_manager.minio_manager import MinioManager

logger = logging.getLogger(__name__)


async def startup_dependencies(app: FastAPI) -> None:
    try:
        logger.info("Starting up dependencies")

        database_manager = DatabaseManager()
        await database_manager.initialize()
        app.state.db_manager = database_manager

        minio_manager = MinioManager()
        await minio_manager.start()
        app.state.minio_manager = minio_manager

        document_storage = DocumentStorage(
            minio_manager=minio_manager
        )
        await document_storage.start()
        app.state.document_storage = document_storage

        http_client = HttpClient()
        await http_client.start()
        app.state.http_client = http_client

        authentication_provider = AuthenticationProvider(
            http_client=http_client
        )
        app.state.authentication_provider = authentication_provider

        document_repository: DocumentRepository = DocumentRepository()
        app.state.document_repository = document_repository

        fragment_repository: FragmentRepository = FragmentRepository()
        app.state.fragment_repository = fragment_repository

        embedder_factory = EmbedderFactory()
        app.state.embedder_factory = embedder_factory

        reader_factory = ReaderFactory()
        app.state.reader_factory = reader_factory

        text_cleaner_factory = TextCleanerFactory()
        app.state.text_cleaner_factory = text_cleaner_factory

        text_splitter_factory = TextSplitterFactory()
        app.state.text_splitter_factory = text_splitter_factory

        document_query_service = DocumentQueryService(
            document_repository=document_repository
        )
        app.state.document_query_service = document_query_service

        fragment_query_service = FragmentQueryService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            embedder_factory=embedder_factory
        )
        app.state.fragment_query_service = fragment_query_service

        document_ingestion_service = DocumentIngestionService(
            database_manager=database_manager,
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            reader_factory=reader_factory,
            text_cleaner_factory=text_cleaner_factory,
            text_splitter_factory=text_splitter_factory,
            embedder_factory=embedder_factory
        )
        app.state.document_ingestion_service = document_ingestion_service

        delete_document_service = DeleteDocumentService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            document_storage=document_storage
        )
        app.state.delete_document_service = delete_document_service

        create_document_service = CreateDocumentService(
            document_repository=document_repository,
            document_storage=document_storage,
            document_ingestion_service=document_ingestion_service
        )
        app.state.create_document_service = create_document_service

        llm_provider = LlmProvider(
            http_client=http_client
        )
        app.state.llm_provider = llm_provider

        post_process_document_service = PostProcessDocumentService(
            database_manager=database_manager,
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            llm_provider=llm_provider
        )
        app.state.post_process_document_service = post_process_document_service

        post_process_fragment_service = PostProcessFragmentService(
            database_manager=database_manager,
            fragment_repository=fragment_repository,
            llm_provider=llm_provider
        )
        app.state.post_process_fragment_service = post_process_fragment_service

        logger.info("All dependencies started successfully")

    except Exception:
        logger.critical("Error during dependency starting up")
        raise


async def shutdown_dependencies() -> None:
    try:
        logger.info("Shutting down dependencies")

        logger.info("All dependencies shut down successfully")

    except Exception:
        logger.error("Error during dependency shutdown")
        raise
