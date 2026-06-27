import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any
from fastapi import FastAPI

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.rerankers.reranker_factory import RerankerFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.services.document.create_document_service.create_document_service import CreateDocumentService
from app.application.services.document.document_download_service.document_download_service import (
    DocumentDownloadService,
)
from app.application.services.document.document_ingestion_service.document_ingestion_service import (
    DocumentIngestionService,
)
from app.application.services.document.document_enrichment_service.document_enrichment_service import (
    DocumentEnrichmentService,
)
from app.application.services.document.bulk_create_document_service.bulk_create_document_service import (
    BulkCreateDocumentService,
)
from app.application.services.document.bulk_dispatch_service.bulk_dispatch_service import BulkDispatchService
from app.application.services.document.delete_document_service.delete_document_service import DeleteDocumentService
from app.application.services.document.restore_document_service.restore_document_service import RestoreDocumentService
from app.application.services.document.update_document_service.update_document_service import UpdateDocumentService
from app.application.services.document.document_query_service.document_query_service import DocumentQueryService
from app.application.services.document.document_search_service.document_search_service import DocumentSearchService
from app.application.services.document.reembed_document_service.reembed_document_service import ReembedDocumentService
from app.application.services.document.reprocess_document_service.reprocess_document_service import (
    ReprocessDocumentService,
)
from app.application.services.document.post_process_document_service.post_process_document_service import (
    PostProcessDocumentService,
)
from app.application.services.fragment.fragment_query_service.fragment_query_service import FragmentQueryService
from app.application.services.fragment.contextualize_fragment_service.contextualize_fragment_processor import (
    ContextualizeFragmentProcessor,
)
from app.application.services.graph.graph_context_service.graph_context_service import GraphContextService
from app.application.services.graph.graph_entity_service.graph_entity_service import GraphEntityService
from app.application.services.graph.graph_extraction_service.graph_extraction_service import (
    GraphExtractionService,
)
from app.application.services.graph.graph_ontology_service.graph_ontology_service import GraphOntologyService
from app.application.services.graph.graph_path_service.graph_path_service import GraphPathService
from app.application.services.graph.graph_query_service.graph_query_service import GraphQueryService
from app.application.services.graph.graph_stats_service.graph_stats_service import GraphStatsService
from app.application.services.graph.knowledge_graph_settings import KnowledgeGraphSettings
from app.infrastructure.http.authentication_provider.authentication_provider import AuthenticationProvider
from app.infrastructure.http.document_collection_catalog.document_collection_catalog_client import (
    DocumentCollectionCatalogClient,
)
from app.infrastructure.http.http_client.http_client import HttpClient
from app.infrastructure.http.llm_provider.llm_provider import LlmProvider
from app.infrastructure.messaging.rabbitmq.consumer.document_ingestion_consumer import DocumentIngestionConsumer
from app.infrastructure.messaging.rabbitmq.consumer.document_enrichment_consumer import DocumentEnrichmentConsumer
from app.infrastructure.messaging.rabbitmq.consumer.document_purge_consumer import DocumentPurgeConsumer
from app.infrastructure.messaging.rabbitmq.consumer.document_reembed_consumer import DocumentReembedConsumer
from app.infrastructure.messaging.rabbitmq.consumer.document_reprocess_consumer import DocumentReprocessConsumer
from app.infrastructure.messaging.rabbitmq.consumer.graph_extraction_consumer import GraphExtractionConsumer
from app.infrastructure.messaging.rabbitmq.publisher.graph_extraction_publisher import (
    GraphExtractionPublisher,
)
from app.infrastructure.messaging.rabbitmq.publisher.document_enrichment_publisher import (
    DocumentEnrichmentPublisher,
)
from app.infrastructure.messaging.rabbitmq.publisher.document_purge_publisher import (
    DocumentPurgePublisher,
)
from app.infrastructure.messaging.rabbitmq.publisher.document_reembed_publisher import (
    DocumentReembedPublisher,
)
from app.infrastructure.messaging.rabbitmq.publisher.document_reprocess_publisher import (
    DocumentReprocessPublisher,
)
from app.infrastructure.messaging.rabbitmq.reliable_publish.outbox_lite_worker import OutboxLiteWorker
from app.infrastructure.messaging.rabbitmq.reliable_publish.redis_outbox_lite import RedisOutboxLite
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager import RabbitMQManager
from app.infrastructure.persistence.database.database_manager.database_manager import DatabaseManager
from app.infrastructure.http.chat_membership.chat_membership_provider import ChatMembershipProvider
from app.infrastructure.persistence.database.repositories.document_repository import (
    DocumentRepository,
)
from app.infrastructure.persistence.database.repositories.fragment_repository import (
    FragmentRepository,
)
from app.infrastructure.persistence.graph.neo4j_manager.neo4j_manager import Neo4jManager
from app.infrastructure.persistence.graph.neo4j_manager.exceptions.neo4j_manager_exception import \
    Neo4jConnectionException
from app.infrastructure.persistence.graph.repositories.graph_entity_repository import (
    GraphEntityRepository,
)
from app.infrastructure.persistence.graph.repositories.graph_path_repository import (
    GraphPathRepository,
)
from app.infrastructure.persistence.graph.repositories.graph_relation_repository import (
    GraphRelationRepository,
)
from app.infrastructure.persistence.graph.repositories.graph_stats_repository import (
    GraphStatsRepository,
)
from app.infrastructure.persistence.memory_database.graph_extraction_lock_store.graph_extraction_lock_store import (
    GraphExtractionLockStore,
)
from app.infrastructure.persistence.memory_database.bulk_job_progress_store.bulk_job_progress_store import (
    BulkJobProgressStore,
)
from app.infrastructure.persistence.memory_database.redis_client.interfaces.redis_client_interface import (
    RedisClientInterface,
)
from app.infrastructure.persistence.memory_database.redis_client.redis_client import RedisClient
from app.infrastructure.persistence.storages.document_storage.document_storage import DocumentStorage
from app.infrastructure.persistence.storages.minio_manager.minio_manager import MinioManager

logger = logging.getLogger(__name__)

_CleanupFn = Callable[[], Awaitable[None]]


class DependencyContainer:
    def __init__(self, app: FastAPI) -> None:
        self._app = app
        self._cleanup_stack: list[tuple[str, _CleanupFn]] = []
        self._state_keys: list[str] = []

    @property
    def app(self) -> FastAPI:
        return self._app

    def register(self, name: str, value: Any, *, cleanup: _CleanupFn | None = None) -> Any:
        setattr(self._app.state, name, value)
        self._state_keys.append(name)
        if cleanup is not None:
            self._cleanup_stack.append((name, cleanup))
        return value

    def get(self, name: str, default: Any = None) -> Any:
        return getattr(self._app.state, name, default)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return getattr(self._app.state, name)
        except AttributeError as e:
            raise AttributeError(
                f"Dependency '{name}' has not been registered yet."
            ) from e

    def mark_started(self) -> None:
        self._cleanup_stack.clear()

    async def rollback(self) -> None:
        while self._cleanup_stack:
            name, fn = self._cleanup_stack.pop()
            try:
                await fn()
            except Exception:
                logger.exception(
                    "Startup rollback: cleanup step failed (continuing with remaining steps).",
                    extra={"resource": name},
                )

        for key in reversed(self._state_keys):
            if hasattr(self._app.state, key):
                try:
                    delattr(self._app.state, key)
                except Exception:
                    logger.warning(
                        "Startup rollback: could not remove app.state attribute.",
                        extra={"key": key},
                    )
        self._state_keys.clear()


async def _warmup_reranker(reranker_factory: RerankerFactory) -> None:
    try:
        reranker = reranker_factory.reranker
        warmup = getattr(reranker, "warmup", None)
        if warmup is not None:
            await warmup()
            logger.info("The reranker model was warmed up successfully.")
    except Exception:
        logger.warning(
            "Reranker warmup failed; the model will be loaded lazily on first use.",
            exc_info=True,
        )


async def _build_persistence(c: DependencyContainer) -> None:
    database_manager = DatabaseManager()
    await database_manager.initialize()
    c.register("db_manager", database_manager, cleanup=database_manager.dispose)

    minio_manager = MinioManager()
    await minio_manager.start()
    c.register("minio_manager", minio_manager, cleanup=minio_manager.stop)

    document_storage = DocumentStorage(minio_manager=minio_manager)
    await document_storage.start()
    c.register("document_storage", document_storage)

    http_client = HttpClient()
    await http_client.start()
    c.register("http_client", http_client, cleanup=http_client.stop)

    redis_client: RedisClientInterface = RedisClient()
    await redis_client.initialize()
    c.register("redis_client", redis_client, cleanup=redis_client.dispose)


def _build_clients_and_repositories(c: DependencyContainer) -> None:
    http_client = c.http_client
    redis_client = c.redis_client

    c.register(
        "authentication_provider",
        AuthenticationProvider(
            http_client=http_client,
            redis_client=redis_client.client,
        ),
    )

    c.register(
        "document_collection_catalog_client",
        DocumentCollectionCatalogClient(http_client=http_client),
    )

    c.register(
        "chat_membership_provider",
        ChatMembershipProvider(http_client=http_client),
    )

    c.register("document_repository", DocumentRepository())
    c.register("fragment_repository", FragmentRepository())


async def _build_processors_and_read_services(c: DependencyContainer) -> None:
    embedder_factory = EmbedderFactory()
    await asyncio.to_thread(lambda: embedder_factory.embedder)
    c.register("embedder_factory", embedder_factory)

    c.register("reader_factory", ReaderFactory())

    text_cleaner_factory = TextCleanerFactory()
    _ = text_cleaner_factory.cleaner
    c.register("text_cleaner_factory", text_cleaner_factory)

    text_splitter_factory = TextSplitterFactory()

    await asyncio.to_thread(text_splitter_factory.warmup)
    c.register("text_splitter_factory", text_splitter_factory)

    c.register(
        "document_query_service",
        DocumentQueryService(
            document_repository=c.document_repository,
            document_collection_catalog_client=c.document_collection_catalog_client,
            chat_membership_provider=c.chat_membership_provider,
        ),
    )

    reranker_factory = RerankerFactory()
    c.register("reranker_factory", reranker_factory)
    c.register(
        "reranker_warmup_task",
        asyncio.create_task(_warmup_reranker(reranker_factory)),
    )

    c.register(
        "fragment_query_service",
        FragmentQueryService(
            document_repository=c.document_repository,
            fragment_repository=c.fragment_repository,
            embedder_factory=c.embedder_factory,
            reranker_factory=reranker_factory,
            document_collection_catalog_client=c.document_collection_catalog_client,
            chat_membership_provider=c.chat_membership_provider,
            database_manager=c.db_manager,
        ),
    )

    c.register(
        "document_search_service",
        DocumentSearchService(
            document_repository=c.document_repository,
            fragment_repository=c.fragment_repository,
            embedder_factory=c.embedder_factory,
            document_collection_catalog_client=c.document_collection_catalog_client,
            reranker_factory=reranker_factory,
        ),
    )


async def _build_messaging(c: DependencyContainer) -> None:
    rabbitmq_manager = RabbitMQManager()
    await rabbitmq_manager.start()
    c.register("rabbitmq_manager", rabbitmq_manager, cleanup=rabbitmq_manager.stop)

    outbox_lite = RedisOutboxLite(
        redis_client=c.redis_client.client,
        rabbitmq_manager=rabbitmq_manager,
    )
    c.register("outbox_lite", outbox_lite)

    c.register(
        "bulk_job_progress_store",
        BulkJobProgressStore(redis_client=c.redis_client.client),
    )

    c.register(
        "document_purge_publisher",
        DocumentPurgePublisher(
            rabbitmq_manager=rabbitmq_manager,
            outbox_lite=outbox_lite,
        ),
    )

    knowledge_graph_settings = KnowledgeGraphSettings()
    c.register("knowledge_graph_settings", knowledge_graph_settings)

    if knowledge_graph_settings.enabled:
        c.register(
            "graph_extraction_publisher",
            GraphExtractionPublisher(
                rabbitmq_manager=rabbitmq_manager,
                outbox_lite=outbox_lite,
            ),
        )
        logger.info(
            "Knowledge graph extraction publisher was registered.",
            extra={"queue": rabbitmq_manager.settings.graph_extraction_queue},
        )


async def _build_document_services(c: DependencyContainer) -> None:
    rabbitmq_manager = c.rabbitmq_manager
    outbox_lite = c.outbox_lite
    database_manager = c.db_manager
    document_repository = c.document_repository
    fragment_repository = c.fragment_repository

    c.register("llm_provider", LlmProvider(http_client=c.http_client))

    c.register(
        "post_process_document_service",
        PostProcessDocumentService(
            database_manager=database_manager,
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            llm_provider=c.llm_provider,
        ),
    )

    c.register(
        "contextualize_fragment_processor",
        ContextualizeFragmentProcessor(
            database_manager=database_manager,
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            llm_provider=c.llm_provider,
            embedder_factory=c.embedder_factory,
        ),
    )

    c.register(
        "document_enrichment_service",
        DocumentEnrichmentService(
            post_process_document_service=c.post_process_document_service,
            contextualize_fragment_processor=c.contextualize_fragment_processor,
            database_manager=database_manager,
            document_repository=document_repository,
        ),
    )

    c.register(
        "document_enrichment_publisher",
        DocumentEnrichmentPublisher(
            rabbitmq_manager=rabbitmq_manager,
            outbox_lite=outbox_lite,
        ),
    )

    c.register(
        "document_ingestion_service",
        DocumentIngestionService(
            database_manager=database_manager,
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            reader_factory=c.reader_factory,
            text_cleaner_factory=c.text_cleaner_factory,
            text_splitter_factory=c.text_splitter_factory,
            embedder_factory=c.embedder_factory,
            graph_extraction_publisher=c.get("graph_extraction_publisher"),
            document_enrichment_publisher=c.document_enrichment_publisher,
        ),
    )

    document_ingestion_consumer = DocumentIngestionConsumer(
        rabbitmq_manager=rabbitmq_manager,
        document_storage=c.document_storage,
        database_manager=database_manager,
        document_repository=document_repository,
        document_ingestion_service=c.document_ingestion_service,
        redis_client=c.redis_client.client,
    )
    await document_ingestion_consumer.start()
    c.register("document_ingestion_consumer", document_ingestion_consumer)

    document_enrichment_consumer = DocumentEnrichmentConsumer(
        rabbitmq_manager=rabbitmq_manager,
        document_enrichment_service=c.document_enrichment_service,
        bulk_job_progress_store=c.bulk_job_progress_store,
    )
    await document_enrichment_consumer.start()
    c.register("document_enrichment_consumer", document_enrichment_consumer)

    outbox_lite_worker = OutboxLiteWorker(
        outbox=outbox_lite,
        database_manager=database_manager,
        document_repository=document_repository,
        rabbitmq_settings=rabbitmq_manager.settings,
    )
    await outbox_lite_worker.start()
    c.register("outbox_lite_worker", outbox_lite_worker, cleanup=outbox_lite_worker.stop)

    c.register(
        "delete_document_service",
        DeleteDocumentService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            chat_membership_provider=c.chat_membership_provider,
            document_purge_publisher=c.document_purge_publisher,
        ),
    )

    c.register(
        "restore_document_service",
        RestoreDocumentService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
        ),
    )

    c.register(
        "update_document_service",
        UpdateDocumentService(
            document_repository=document_repository,
        ),
    )

    c.register(
        "create_document_service",
        CreateDocumentService(
            document_repository=document_repository,
            document_storage=c.document_storage,
            rabbitmq_manager=rabbitmq_manager,
            outbox_lite=outbox_lite,
        ),
    )

    c.register(
        "bulk_create_document_service",
        BulkCreateDocumentService(
            create_document_service=c.create_document_service,
            database_manager=database_manager,
        ),
    )

    c.register(
        "document_download_service",
        DocumentDownloadService(
            document_repository=document_repository,
            document_storage=c.document_storage,
            document_collection_catalog_client=c.document_collection_catalog_client,
            chat_membership_provider=c.chat_membership_provider,
        ),
    )

    await _build_maintenance_pipelines(c)


async def _build_maintenance_pipelines(c: DependencyContainer) -> None:
    rabbitmq_manager = c.rabbitmq_manager
    outbox_lite = c.outbox_lite

    c.register(
        "document_reembed_publisher",
        DocumentReembedPublisher(rabbitmq_manager=rabbitmq_manager, outbox_lite=outbox_lite),
    )
    c.register(
        "document_reprocess_publisher",
        DocumentReprocessPublisher(rabbitmq_manager=rabbitmq_manager, outbox_lite=outbox_lite),
    )

    c.register(
        "reembed_document_service",
        ReembedDocumentService(
            document_repository=c.document_repository,
            fragment_repository=c.fragment_repository,
            embedder_factory=c.embedder_factory,
            database_manager=c.db_manager,
        ),
    )
    c.register(
        "reprocess_document_service",
        ReprocessDocumentService(
            document_repository=c.document_repository,
            fragment_repository=c.fragment_repository,
            document_storage=c.document_storage,
            document_ingestion_service=c.document_ingestion_service,
            database_manager=c.db_manager,
        ),
    )

    document_reembed_consumer = DocumentReembedConsumer(
        rabbitmq_manager=rabbitmq_manager,
        reembed_document_service=c.reembed_document_service,
        redis_client=c.redis_client.client,
        bulk_job_progress_store=c.bulk_job_progress_store,
    )
    await document_reembed_consumer.start()
    c.register("document_reembed_consumer", document_reembed_consumer)

    document_reprocess_consumer = DocumentReprocessConsumer(
        rabbitmq_manager=rabbitmq_manager,
        reprocess_document_service=c.reprocess_document_service,
        redis_client=c.redis_client.client,
        bulk_job_progress_store=c.bulk_job_progress_store,
    )
    await document_reprocess_consumer.start()
    c.register("document_reprocess_consumer", document_reprocess_consumer)

    c.register(
        "bulk_dispatch_service",
        BulkDispatchService(
            database_manager=c.db_manager,
            document_repository=c.document_repository,
            progress_store=c.bulk_job_progress_store,
            reembed_publisher=c.document_reembed_publisher,
            reprocess_publisher=c.document_reprocess_publisher,
            enrichment_publisher=c.document_enrichment_publisher,
            graph_extraction_publisher=c.get("graph_extraction_publisher"),
        ),
    )


async def _build_purge_consumer(c: DependencyContainer) -> None:
    document_purge_consumer = DocumentPurgeConsumer(
        rabbitmq_manager=c.rabbitmq_manager,
        database_manager=c.db_manager,
        document_repository=c.document_repository,
        document_storage=c.document_storage,
        graph_entity_repository=c.get("graph_entity_repository"),
        graph_relation_repository=c.get("graph_relation_repository"),
    )
    await document_purge_consumer.start()
    c.register("document_purge_consumer", document_purge_consumer)


async def startup_dependencies(app: FastAPI) -> None:
    container = DependencyContainer(app)
    try:
        logger.info("Starting up dependencies")

        await _build_persistence(container)
        _build_clients_and_repositories(container)
        await _build_processors_and_read_services(container)
        await _build_messaging(container)
        await _build_document_services(container)

        knowledge_graph_settings = container.knowledge_graph_settings
        if knowledge_graph_settings.enabled:
            await _wire_knowledge_graph_module(container)
        else:
            logger.info("Knowledge graph module is disabled (KNOWLEDGE_GRAPH_ENABLED=false); skipping Neo4j bootstrap.")

        await _build_purge_consumer(container)

        logger.info("All dependencies started successfully")
        container.mark_started()

    except Exception:
        logger.critical("Error during dependency starting up; rolling back started resources in reverse order.")
        await container.rollback()
        raise


async def _wire_knowledge_graph_module(c: DependencyContainer) -> None:
    knowledge_graph_settings = c.knowledge_graph_settings

    logger.info(
        "Bootstrapping the knowledge graph module.",
        extra={
            "extraction_concurrency": knowledge_graph_settings.extraction_concurrency,
        },
    )

    neo4j_manager = Neo4jManager()
    try:
        await neo4j_manager.start()
    except Neo4jConnectionException:
        logger.warning(
            "Neo4j is unavailable; the knowledge graph module will be disabled for this run.",
            extra={"uri": neo4j_manager.settings.uri_safe},
        )
        return
    c.register("neo4j_manager", neo4j_manager, cleanup=neo4j_manager.dispose)

    c.register("graph_entity_repository", GraphEntityRepository(neo4j_manager=neo4j_manager))

    c.register(
        "graph_relation_repository",
        GraphRelationRepository(
            neo4j_manager=neo4j_manager,
            max_depth=knowledge_graph_settings.query_max_neighbor_depth,
        ),
    )

    c.register("graph_path_repository", GraphPathRepository(neo4j_manager=neo4j_manager))

    c.register(
        "graph_extraction_lock_store",
        GraphExtractionLockStore(
            redis_client=c.redis_client.client,
            lock_ttl_seconds=knowledge_graph_settings.extraction_lock_ttl_seconds,
        ),
    )

    c.register(
        "graph_extraction_service",
        GraphExtractionService(
            database_manager=c.db_manager,
            document_repository=c.document_repository,
            fragment_repository=c.fragment_repository,
            llm_provider=c.llm_provider,
            entity_repository=c.graph_entity_repository,
            relation_repository=c.graph_relation_repository,
            lock_store=c.graph_extraction_lock_store,
            knowledge_graph_settings=knowledge_graph_settings,
        ),
    )

    graph_extraction_consumer = GraphExtractionConsumer(
        rabbitmq_manager=c.rabbitmq_manager,
        graph_extraction_service=c.graph_extraction_service,
        bulk_job_progress_store=c.bulk_job_progress_store,
    )
    await graph_extraction_consumer.start()
    c.register("graph_extraction_consumer", graph_extraction_consumer)

    c.register(
        "graph_query_service",
        GraphQueryService(
            llm_provider=c.llm_provider,
            entity_repository=c.graph_entity_repository,
            relation_repository=c.graph_relation_repository,
            path_repository=c.graph_path_repository,
            document_collection_catalog_client=c.document_collection_catalog_client,
            knowledge_graph_settings=knowledge_graph_settings,
        ),
    )

    c.register(
        "graph_entity_service",
        GraphEntityService(
            entity_repository=c.graph_entity_repository,
            relation_repository=c.graph_relation_repository,
            document_collection_catalog_client=c.document_collection_catalog_client,
            knowledge_graph_settings=knowledge_graph_settings,
        ),
    )

    c.register(
        "graph_context_service",
        GraphContextService(
            entity_repository=c.graph_entity_repository,
            relation_repository=c.graph_relation_repository,
            document_collection_catalog_client=c.document_collection_catalog_client,
            knowledge_graph_settings=knowledge_graph_settings,
        ),
    )

    c.register(
        "graph_path_service",
        GraphPathService(
            path_repository=c.graph_path_repository,
            document_collection_catalog_client=c.document_collection_catalog_client,
            knowledge_graph_settings=knowledge_graph_settings,
        ),
    )

    c.register("graph_stats_repository", GraphStatsRepository(neo4j_manager=neo4j_manager))

    c.register(
        "graph_stats_service",
        GraphStatsService(stats_repository=c.graph_stats_repository),
    )

    c.register("graph_ontology_service", GraphOntologyService())

    logger.info("The knowledge graph module was bootstrapped successfully.")


async def shutdown_dependencies(app: FastAPI) -> None:
    logger.info("Shutting down dependencies")

    state = app.state

    if outbox_lite_worker := getattr(state, "outbox_lite_worker", None):
        await outbox_lite_worker.stop()

    if rabbitmq_manager := getattr(state, "rabbitmq_manager", None):
        await rabbitmq_manager.stop()

    if neo4j_manager := getattr(state, "neo4j_manager", None):
        try:
            await neo4j_manager.dispose()
        except Exception:
            logger.exception("Failed to dispose the Neo4j manager during shutdown.")

    if redis_client := getattr(state, "redis_client", None):
        await redis_client.dispose()

    if http_client := getattr(state, "http_client", None):
        await http_client.stop()

    if minio_manager := getattr(state, "minio_manager", None):
        await minio_manager.stop()

    if db_manager := getattr(state, "db_manager", None):
        await db_manager.dispose()

    logger.info("All dependencies shut down successfully")
