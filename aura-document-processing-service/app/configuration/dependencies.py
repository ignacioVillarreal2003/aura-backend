import logging
from typing import Optional

import redis.asyncio as aioredis
from fastapi import FastAPI

import app.configuration.prometheus_post_process_metrics  # noqa: F401 — register custom metrics

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.authorization.authorizer import Authorizer
from app.application.coordination.interfaces.content_deduplication_port_interface import (
    ContentDeduplicationPortInterface,
)
from app.application.coordination.interfaces.distributed_lock_port_interface import (
    DistributedLockPortInterface,
)
from app.application.coordination.interfaces.post_process_job_progress_store_interface import (
    PostProcessJobProgressStoreInterface,
)
from app.application.services.document.create_document_service.create_document_service import CreateDocumentService
from app.application.services.document.document_download_service.document_download_service import DocumentDownloadService
from app.application.services.document.document_ingestion_service.document_ingestion_service import (
    DocumentIngestionService,
)
from app.application.services.document.delete_document_service.delete_document_service import DeleteDocumentService
from app.application.services.document.document_query_service.document_query_service import DocumentQueryService
from app.application.services.document.post_process_document_runner.post_process_document_runner import (
    PostProcessDocumentRunner,
)
from app.application.services.document.post_process_document_service.post_process_document_service import (
    PostProcessDocumentService,
)
from app.application.services.fragment.fragment_query_service.fragment_query_service import FragmentQueryService
from app.application.services.fragment.post_process_fragment_runner.post_process_fragment_runner import (
    PostProcessFragmentRunner,
)
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_service import (
    PostProcessFragmentService,
)
from app.configuration.coordination_settings import CoordinationSettings
from app.infrastructure.coordination.memory_content_deduplication_port import MemoryContentDeduplicationPort
from app.infrastructure.coordination.memory_distributed_lock_port import MemoryDistributedLockPort
from app.infrastructure.coordination.memory_post_process_job_progress_store import MemoryPostProcessJobProgressStore
from app.infrastructure.coordination.redis_content_deduplication_port import RedisContentDeduplicationPort
from app.infrastructure.coordination.redis_distributed_lock_port import RedisDistributedLockPort
from app.infrastructure.coordination.redis_post_process_job_progress_store import RedisPostProcessJobProgressStore
from app.infrastructure.http.authentication_provider.authentication_provider import AuthenticationProvider
from app.infrastructure.http.http_client.http_client import HttpClient
from app.infrastructure.http.llm_provider.llm_provider import LlmProvider
from app.infrastructure.messaging.rabbitmq.consumer.document_ingestion_consumer import DocumentIngestionConsumer
from app.infrastructure.messaging.rabbitmq.consumer.post_process_document_consumer import PostProcessDocumentConsumer
from app.infrastructure.messaging.rabbitmq.consumer.post_process_fragment_consumer import PostProcessFragmentConsumer
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager import RabbitMQManager
from app.infrastructure.persistence.database.database_manager.database_manager import DatabaseManager
from app.infrastructure.persistence.database.repositories.document_collection_repository.document_collection_repository import (
    DocumentCollectionRepository,
)
from app.infrastructure.persistence.database.repositories.document_repository.document_repository import (
    DocumentRepository,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository import (
    FragmentRepository,
)
from app.infrastructure.persistence.storages.document_storage.document_storage import DocumentStorage
from app.infrastructure.persistence.storages.minio_manager.minio_manager import MinioManager

logger = logging.getLogger(__name__)


async def startup_dependencies(app: FastAPI) -> None:
    try:
        logger.info("Starting up dependencies")

        coordination_settings = CoordinationSettings()
        app.state.coordination_settings = coordination_settings

        redis_client: Optional[aioredis.Redis] = None
        if (
                coordination_settings.post_process_progress_backend == "redis"
                or coordination_settings.content_deduplication_backend == "redis"
                or coordination_settings.distributed_lock_backend == "redis"
        ):
            redis_client = aioredis.from_url(
                coordination_settings.redis_url.get_secret_value(),  # type: ignore[union-attr]
                decode_responses=True,
            )
            await redis_client.ping()
            app.state.redis_client = redis_client
        else:
            app.state.redis_client = None

        if coordination_settings.post_process_progress_backend == "redis":
            job_progress_store: PostProcessJobProgressStoreInterface = RedisPostProcessJobProgressStore(
                redis_client=redis_client,  # type: ignore[arg-type]
                coordination_settings=coordination_settings,
            )
        else:
            job_progress_store = MemoryPostProcessJobProgressStore()
        app.state.post_process_job_progress_store = job_progress_store

        if coordination_settings.content_deduplication_backend == "redis":
            content_deduplication: ContentDeduplicationPortInterface = RedisContentDeduplicationPort(
                redis_client=redis_client,  # type: ignore[arg-type]
                coordination_settings=coordination_settings,
            )
        else:
            content_deduplication = MemoryContentDeduplicationPort()
        app.state.content_deduplication = content_deduplication

        if coordination_settings.distributed_lock_backend == "redis":
            distributed_lock: DistributedLockPortInterface = RedisDistributedLockPort(
                redis_client=redis_client,  # type: ignore[arg-type]
                coordination_settings=coordination_settings,
            )
        else:
            distributed_lock = MemoryDistributedLockPort()
        app.state.distributed_lock = distributed_lock

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

        document_collection_repository: DocumentCollectionRepository = DocumentCollectionRepository()
        app.state.document_collection_repository = document_collection_repository

        embedder_factory = EmbedderFactory()
        app.state.embedder_factory = embedder_factory

        reader_factory = ReaderFactory()
        app.state.reader_factory = reader_factory

        text_cleaner_factory = TextCleanerFactory()
        app.state.text_cleaner_factory = text_cleaner_factory

        text_splitter_factory = TextSplitterFactory()
        app.state.text_splitter_factory = text_splitter_factory

        authorizer = Authorizer()
        app.state.authorizer = authorizer

        document_query_service = DocumentQueryService(
            document_repository=document_repository,
            authorizer=authorizer
        )
        app.state.document_query_service = document_query_service

        fragment_query_service = FragmentQueryService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            embedder_factory=embedder_factory,
            authorizer=authorizer,
            document_collection_repository=document_collection_repository
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

        rabbitmq_manager = RabbitMQManager()
        await rabbitmq_manager.start()
        app.state.rabbitmq_manager = rabbitmq_manager

        document_ingestion_consumer = DocumentIngestionConsumer(
            rabbitmq_manager=rabbitmq_manager,
            document_storage=document_storage,
            database_manager=database_manager,
            document_repository=document_repository,
            document_ingestion_service=document_ingestion_service,
        )
        await document_ingestion_consumer.start()
        app.state.document_ingestion_consumer = document_ingestion_consumer

        llm_provider = LlmProvider(
            http_client=http_client
        )
        app.state.llm_provider = llm_provider

        post_process_document_runner = PostProcessDocumentRunner(
            database_manager=database_manager,
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            llm_provider=llm_provider,
        )
        app.state.post_process_document_runner = post_process_document_runner

        post_process_fragment_runner = PostProcessFragmentRunner(
            database_manager=database_manager,
            fragment_repository=fragment_repository,
            llm_provider=llm_provider,
        )
        app.state.post_process_fragment_runner = post_process_fragment_runner

        post_process_document_consumer = PostProcessDocumentConsumer(
            rabbitmq_manager=rabbitmq_manager,
            job_progress_store=job_progress_store,
            runner=post_process_document_runner,
        )
        await post_process_document_consumer.start()
        app.state.post_process_document_consumer = post_process_document_consumer

        post_process_fragment_consumer = PostProcessFragmentConsumer(
            rabbitmq_manager=rabbitmq_manager,
            job_progress_store=job_progress_store,
            runner=post_process_fragment_runner,
        )
        await post_process_fragment_consumer.start()
        app.state.post_process_fragment_consumer = post_process_fragment_consumer

        delete_document_service = DeleteDocumentService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            document_storage=document_storage,
            authorizer=authorizer
        )
        app.state.delete_document_service = delete_document_service

        create_document_service = CreateDocumentService(
            document_repository=document_repository,
            document_storage=document_storage,
            rabbitmq_manager=rabbitmq_manager,
            authorizer=authorizer,
            content_deduplication=content_deduplication,
        )
        app.state.create_document_service = create_document_service

        document_download_service = DocumentDownloadService(
            document_repository=document_repository,
            document_storage=document_storage,
            authorizer=authorizer
        )
        app.state.document_download_service = document_download_service

        post_process_document_service = PostProcessDocumentService(
            database_manager=database_manager,
            document_repository=document_repository,
            rabbitmq_manager=rabbitmq_manager,
            job_progress_store=job_progress_store,
            authorizer=authorizer,
        )
        app.state.post_process_document_service = post_process_document_service

        post_process_fragment_service = PostProcessFragmentService(
            database_manager=database_manager,
            fragment_repository=fragment_repository,
            rabbitmq_manager=rabbitmq_manager,
            job_progress_store=job_progress_store,
            authorizer=authorizer,
        )
        app.state.post_process_fragment_service = post_process_fragment_service

        logger.info("All dependencies started successfully")

    except Exception:
        logger.critical("Error during dependency starting up")
        raise


async def shutdown_dependencies(app: FastAPI) -> None:
    logger.info("Shutting down dependencies")

    state = app.state

    if rabbitmq_manager := getattr(state, "rabbitmq_manager", None):
        await rabbitmq_manager.stop()

    if redis_client := getattr(state, "redis_client", None):
        await redis_client.aclose()

    if http_client := getattr(state, "http_client", None):
        await http_client.stop()

    if minio_manager := getattr(state, "minio_manager", None):
        await minio_manager.stop()

    if db_manager := getattr(state, "db_manager", None):
        await db_manager.dispose()

    logger.info("All dependencies shut down successfully")
