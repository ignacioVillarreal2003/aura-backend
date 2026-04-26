import asyncio
import logging
from collections.abc import Awaitable, Callable
from fastapi import FastAPI

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.authorization.authorizer import Authorizer
from app.application.services.document.create_document_service.create_document_service import CreateDocumentService
from app.application.services.document.document_download_service.document_download_service import DocumentDownloadService
from app.application.services.document.document_ingestion_service.document_ingestion_service import (
    DocumentIngestionService,
)
from app.application.services.document.delete_document_service.delete_document_service import DeleteDocumentService
from app.application.services.document.document_query_service.document_query_service import DocumentQueryService
from app.application.services.document.post_process_document_service.post_process_document_service import (
    PostProcessDocumentService,
)
from app.application.services.document.post_process_document_service.post_process_document_processor import (
    PostProcessDocumentProcessor,
)
from app.application.services.fragment.fragment_query_service.fragment_query_service import FragmentQueryService
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_service import (
    PostProcessFragmentService,
)
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_processor import (
    PostProcessFragmentProcessor,
)
from app.infrastructure.http.authentication_provider.authentication_provider import AuthenticationProvider
from app.infrastructure.http.authentication_provider.authentication_provider_settings import (
    AuthenticationProviderSettings,
)
from app.infrastructure.http.http_client.http_client import HttpClient
from app.infrastructure.http.llm_provider.llm_provider import LlmProvider
from app.infrastructure.messaging.rabbitmq.consumer.document_ingestion_consumer import DocumentIngestionConsumer
from app.infrastructure.messaging.rabbitmq.consumer.post_process_document_consumer import PostProcessDocumentConsumer
from app.infrastructure.messaging.rabbitmq.consumer.post_process_fragment_consumer import PostProcessFragmentConsumer
from app.infrastructure.messaging.rabbitmq.publisher.post_process_document_job_publisher import (
    PostProcessDocumentJobPublisher,
)
from app.infrastructure.messaging.rabbitmq.publisher.post_process_fragment_job_publisher import (
    PostProcessFragmentJobPublisher,
)
from app.infrastructure.messaging.rabbitmq.reliable_publish.outbox_lite_worker import OutboxLiteWorker
from app.infrastructure.messaging.rabbitmq.reliable_publish.redis_outbox_lite import RedisOutboxLite
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager import RabbitMQManager
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager_settings import RabbitMQManagerSettings
from app.infrastructure.persistence.database.database_manager.database_manager import DatabaseManager
from app.infrastructure.persistence.database.repositories.chat_repository.chat_repository import ChatRepository
from app.infrastructure.persistence.database.repositories.document_collection_repository.document_collection_repository import (
    DocumentCollectionRepository,
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository import (
    DocumentRepository,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository import (
    FragmentRepository,
)
from app.infrastructure.persistence.memory_database.redis_client.redis_client import RedisClient
from app.infrastructure.persistence.memory_database.redis_client.redis_client_settings import RedisClientSettings
from app.infrastructure.persistence.memory_database.document_post_process_job_progress_store.document_post_process_job_progress_store import (
    DocumentPostProcessJobProgressStore,
)
from app.infrastructure.persistence.memory_database.fragment_post_process_job_progress_store.fragment_post_process_job_progress_store import (
    FragmentPostProcessJobProgressStore,
)
from app.infrastructure.persistence.storages.document_storage.document_storage import DocumentStorage
from app.infrastructure.persistence.storages.minio_manager.minio_manager import MinioManager

logger = logging.getLogger(__name__)

_CleanupFn = Callable[[], Awaitable[None]]


async def _rollback_partial_startup(
        *,
        cleanup_stack: list[tuple[str, _CleanupFn]],
        app: FastAPI,
) -> None:
    while cleanup_stack:
        name, fn = cleanup_stack.pop()
        try:
            await fn()
        except Exception:
            logger.exception(
                "Startup rollback: cleanup step failed (continuing with remaining steps).",
                extra={"resource": name},
            )
    to_clear = [
        "post_process_fragment_service",
        "post_process_document_service",
        "document_download_service",
        "create_document_service",
        "delete_document_service",
        "post_process_fragment_consumer",
        "post_process_document_consumer",
        "post_process_fragment_processor",
        "post_process_document_processor",
        "outbox_lite_worker",
        "post_process_fragment_job_publisher",
        "post_process_document_job_publisher",
        "llm_provider",
        "document_ingestion_consumer",
        "outbox_lite",
        "rabbitmq_manager",
        "fragment_job_progress_store",
        "document_job_progress_store",
        "redis_client",
        "document_ingestion_service",
        "fragment_query_service",
        "document_query_service",
        "authorizer",
        "text_splitter_factory",
        "text_cleaner_factory",
        "reader_factory",
        "embedder_factory",
        "chat_repository",
        "document_collection_repository",
        "fragment_repository",
        "document_repository",
        "authentication_provider",
        "authentication_provider_settings",
        "http_client",
        "document_storage",
        "minio_manager",
        "db_manager",
    ]
    for key in to_clear:
        if hasattr(app.state, key):
            try:
                delattr(app.state, key)
            except Exception:
                logger.warning(
                    "Startup rollback: could not remove app.state attribute.",
                    extra={"key": key},
                )


async def startup_dependencies(app: FastAPI) -> None:
    cleanup_stack: list[tuple[str, _CleanupFn]] = []
    try:
        logger.info("Starting up dependencies")

        database_manager = DatabaseManager()
        await database_manager.initialize()
        app.state.db_manager = database_manager
        cleanup_stack.append(("database_manager", database_manager.dispose))

        minio_manager = MinioManager()
        await minio_manager.start()
        app.state.minio_manager = minio_manager
        cleanup_stack.append(("minio_manager", minio_manager.stop))

        document_storage = DocumentStorage(minio_manager=minio_manager)
        await document_storage.start()
        app.state.document_storage = document_storage

        http_client = HttpClient()
        await http_client.start()
        app.state.http_client = http_client
        cleanup_stack.append(("http_client", http_client.stop))

        authentication_provider_settings = AuthenticationProviderSettings()
        authentication_provider = AuthenticationProvider(
            http_client=http_client,
            authentication_provider_settings=authentication_provider_settings,
        )
        app.state.authentication_provider_settings = authentication_provider_settings
        app.state.authentication_provider = authentication_provider

        document_repository: DocumentRepository = DocumentRepository()
        app.state.document_repository = document_repository

        fragment_repository: FragmentRepository = FragmentRepository()
        app.state.fragment_repository = fragment_repository

        document_collection_repository: DocumentCollectionRepository = DocumentCollectionRepository()
        app.state.document_collection_repository = document_collection_repository

        chat_repository: ChatRepository = ChatRepository()
        app.state.chat_repository = chat_repository

        embedder_factory = EmbedderFactory()
        await asyncio.to_thread(lambda: embedder_factory.embedder)
        app.state.embedder_factory = embedder_factory

        reader_factory = ReaderFactory()
        app.state.reader_factory = reader_factory

        text_cleaner_factory = TextCleanerFactory()
        text_cleaner_factory.cleaner
        app.state.text_cleaner_factory = text_cleaner_factory

        text_splitter_factory = TextSplitterFactory()
        await asyncio.to_thread(lambda: text_splitter_factory.splitter)
        app.state.text_splitter_factory = text_splitter_factory

        authorizer = Authorizer()
        app.state.authorizer = authorizer

        document_query_service = DocumentQueryService(
            document_repository=document_repository,
            authorizer=authorizer,
        )
        app.state.document_query_service = document_query_service

        fragment_query_service = FragmentQueryService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            embedder_factory=embedder_factory,
            authorizer=authorizer,
            document_collection_repository=document_collection_repository,
        )
        app.state.fragment_query_service = fragment_query_service

        document_ingestion_service = DocumentIngestionService(
            database_manager=database_manager,
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            reader_factory=reader_factory,
            text_cleaner_factory=text_cleaner_factory,
            text_splitter_factory=text_splitter_factory,
            embedder_factory=embedder_factory,
        )
        app.state.document_ingestion_service = document_ingestion_service

        redis_client_settings = RedisClientSettings()
        redis_client = RedisClient(redis_client_settings=redis_client_settings)
        await redis_client.initialize()
        app.state.redis_client = redis_client
        cleanup_stack.append(("redis_client", redis_client.dispose))

        document_job_progress_store = DocumentPostProcessJobProgressStore(
            redis_client=redis_client.client,
            settings=redis_client_settings,
        )
        app.state.document_job_progress_store = document_job_progress_store

        fragment_job_progress_store = FragmentPostProcessJobProgressStore(
            redis_client=redis_client.client,
            settings=redis_client_settings,
        )
        app.state.fragment_job_progress_store = fragment_job_progress_store

        rabbitmq_manager_settings = RabbitMQManagerSettings()
        rabbitmq_manager = RabbitMQManager(rabbit_mq_manager_settings=rabbitmq_manager_settings)
        await rabbitmq_manager.start()
        app.state.rabbitmq_manager = rabbitmq_manager
        cleanup_stack.append(("rabbitmq_manager", rabbitmq_manager.stop))

        outbox_lite = RedisOutboxLite(
            redis_client=redis_client.client,
            rabbitmq_manager=rabbitmq_manager,
            settings=redis_client_settings,
        )
        app.state.outbox_lite = outbox_lite

        document_ingestion_consumer = DocumentIngestionConsumer(
            rabbitmq_manager=rabbitmq_manager,
            document_storage=document_storage,
            database_manager=database_manager,
            document_repository=document_repository,
            document_ingestion_service=document_ingestion_service,
            redis_client=redis_client.client,
        )
        await document_ingestion_consumer.start()
        app.state.document_ingestion_consumer = document_ingestion_consumer

        llm_provider = LlmProvider(http_client=http_client)
        app.state.llm_provider = llm_provider

        post_process_document_job_publisher = PostProcessDocumentJobPublisher(
            rabbitmq_manager=rabbitmq_manager,
            outbox_lite=outbox_lite,
        )
        app.state.post_process_document_job_publisher = post_process_document_job_publisher

        post_process_fragment_job_publisher = PostProcessFragmentJobPublisher(
            rabbitmq_manager=rabbitmq_manager,
            outbox_lite=outbox_lite,
        )
        app.state.post_process_fragment_job_publisher = post_process_fragment_job_publisher

        outbox_lite_worker = OutboxLiteWorker(
            outbox=outbox_lite,
            database_manager=database_manager,
            document_job_progress_store=document_job_progress_store,
            fragment_job_progress_store=fragment_job_progress_store,
            rabbitmq_settings=rabbitmq_manager_settings,
            settings=redis_client_settings,
        )
        await outbox_lite_worker.start()
        app.state.outbox_lite_worker = outbox_lite_worker
        cleanup_stack.append(("outbox_lite_worker", outbox_lite_worker.stop))

        post_process_document_processor = PostProcessDocumentProcessor(
            database_manager=database_manager,
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            llm_provider=llm_provider,
            job_progress_store=document_job_progress_store,
        )
        app.state.post_process_document_processor = post_process_document_processor

        post_process_fragment_processor = PostProcessFragmentProcessor(
            database_manager=database_manager,
            fragment_repository=fragment_repository,
            llm_provider=llm_provider,
            job_progress_store=fragment_job_progress_store,
        )
        app.state.post_process_fragment_processor = post_process_fragment_processor

        post_process_document_consumer = PostProcessDocumentConsumer(
            rabbitmq_manager=rabbitmq_manager,
            processor=post_process_document_processor,
        )
        await post_process_document_consumer.start()
        app.state.post_process_document_consumer = post_process_document_consumer

        post_process_fragment_consumer = PostProcessFragmentConsumer(
            rabbitmq_manager=rabbitmq_manager,
            processor=post_process_fragment_processor,
        )
        await post_process_fragment_consumer.start()
        app.state.post_process_fragment_consumer = post_process_fragment_consumer

        delete_document_service = DeleteDocumentService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            chat_repository=chat_repository,
            authorizer=authorizer,
        )
        app.state.delete_document_service = delete_document_service

        create_document_service = CreateDocumentService(
            document_repository=document_repository,
            document_storage=document_storage,
            rabbitmq_manager=rabbitmq_manager,
            authorizer=authorizer,
            outbox_lite=outbox_lite,
        )
        app.state.create_document_service = create_document_service

        document_download_service = DocumentDownloadService(
            document_repository=document_repository,
            document_storage=document_storage,
            authorizer=authorizer,
        )
        app.state.document_download_service = document_download_service

        post_process_document_service = PostProcessDocumentService(
            database_manager=database_manager,
            document_repository=document_repository,
            job_progress_store=document_job_progress_store,
            post_process_document_job_publisher=post_process_document_job_publisher,
            authorizer=authorizer,
        )
        app.state.post_process_document_service = post_process_document_service

        post_process_fragment_service = PostProcessFragmentService(
            database_manager=database_manager,
            fragment_repository=fragment_repository,
            job_progress_store=fragment_job_progress_store,
            post_process_fragment_job_publisher=post_process_fragment_job_publisher,
            authorizer=authorizer,
        )
        app.state.post_process_fragment_service = post_process_fragment_service

        logger.info("All dependencies started successfully")
        cleanup_stack.clear()

    except Exception:
        logger.critical("Error during dependency starting up; rolling back started resources in reverse order.")
        await _rollback_partial_startup(cleanup_stack=cleanup_stack, app=app)
        raise


async def shutdown_dependencies(app: FastAPI) -> None:
    logger.info("Shutting down dependencies")

    state = app.state

    if outbox_lite_worker := getattr(state, "outbox_lite_worker", None):
        await outbox_lite_worker.stop()

    if rabbitmq_manager := getattr(state, "rabbitmq_manager", None):
        await rabbitmq_manager.stop()

    if redis_client := getattr(state, "redis_client", None):
        await redis_client.dispose()

    if http_client := getattr(state, "http_client", None):
        await http_client.stop()

    if minio_manager := getattr(state, "minio_manager", None):
        await minio_manager.stop()

    if db_manager := getattr(state, "db_manager", None):
        await db_manager.dispose()

    logger.info("All dependencies shut down successfully")
