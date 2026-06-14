import asyncio
import logging
from collections.abc import Awaitable, Callable
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
from app.application.services.document.delete_document_service.delete_document_service import DeleteDocumentService
from app.application.services.document.document_query_service.document_query_service import DocumentQueryService
from app.application.services.document.document_search_service.document_search_service import DocumentSearchService
from app.application.services.document.post_process_document_service.post_process_document_processor import (
    PostProcessDocumentProcessor,
)
from app.application.services.fragment.fragment_query_service.fragment_query_service import FragmentQueryService
from app.application.services.fragment.post_process_fragment_service.post_process_fragment_processor import (
    PostProcessFragmentProcessor,
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
from app.infrastructure.messaging.rabbitmq.consumer.graph_extraction_consumer import GraphExtractionConsumer
from app.infrastructure.messaging.rabbitmq.publisher.graph_extraction_publisher import (
    GraphExtractionPublisher,
)
from app.infrastructure.messaging.rabbitmq.publisher.document_enrichment_publisher import (
    DocumentEnrichmentPublisher,
)
from app.infrastructure.messaging.rabbitmq.reliable_publish.outbox_lite_worker import OutboxLiteWorker
from app.infrastructure.messaging.rabbitmq.reliable_publish.redis_outbox_lite import RedisOutboxLite
from app.infrastructure.messaging.rabbitmq.rabbitmq_manager import RabbitMQManager
from app.infrastructure.persistence.database.database_manager.database_manager import DatabaseManager
from app.infrastructure.http.chat_membership.chat_membership_provider import ChatMembershipProvider
from app.infrastructure.persistence.database.repositories.document_repository.document_repository import (
    DocumentRepository,
)
from app.infrastructure.persistence.database.repositories.fragment_repository.fragment_repository import (
    FragmentRepository,
)
from app.infrastructure.persistence.graph.neo4j_manager.neo4j_manager import Neo4jManager
from app.infrastructure.persistence.graph.neo4j_manager.exceptions.neo4j_manager_exception import Neo4jConnectionException
from app.infrastructure.persistence.graph.repositories.graph_entity_repository.graph_entity_repository import (
    GraphEntityRepository,
)
from app.infrastructure.persistence.graph.repositories.graph_path_repository.graph_path_repository import (
    GraphPathRepository,
)
from app.infrastructure.persistence.graph.repositories.graph_relation_repository.graph_relation_repository import (
    GraphRelationRepository,
)
from app.infrastructure.persistence.graph.repositories.graph_stats_repository.graph_stats_repository import (
    GraphStatsRepository,
)
from app.infrastructure.persistence.memory_database.graph_extraction_job_progress_store.graph_extraction_job_progress_store import (
    GraphExtractionJobProgressStore,
)
from app.infrastructure.persistence.memory_database.redis_client.interfaces.redis_client_interface import (
    RedisClientInterface,
)
from app.infrastructure.persistence.memory_database.redis_client.redis_client import RedisClient
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
        "graph_ontology_service",
        "graph_stats_service",
        "graph_stats_repository",
        "graph_path_service",
        "graph_context_service",
        "graph_entity_service",
        "graph_query_service",
        "graph_extraction_service",
        "graph_extraction_consumer",
        "graph_extraction_publisher",
        "graph_path_repository",
        "graph_relation_repository",
        "graph_entity_repository",
        "graph_extraction_job_progress_store",
        "neo4j_manager",
        "knowledge_graph_settings",
        "document_download_service",
        "create_document_service",
        "delete_document_service",
        "document_enrichment_consumer",
        "document_enrichment_publisher",
        "document_enrichment_service",
        "post_process_fragment_processor",
        "post_process_document_processor",
        "outbox_lite_worker",
        "llm_provider",
        "document_ingestion_consumer",
        "outbox_lite",
        "rabbitmq_manager",
        "redis_client",
        "document_ingestion_service",
        "document_search_service",
        "fragment_query_service",
        "document_query_service",
        "text_splitter_factory",
        "text_cleaner_factory",
        "reader_factory",
        "embedder_factory",
        "chat_membership_provider",
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

        redis_client: RedisClientInterface = RedisClient()
        await redis_client.initialize()
        app.state.redis_client = redis_client
        cleanup_stack.append(("redis_client", redis_client.dispose))

        authentication_provider = AuthenticationProvider(
            http_client=http_client,
            redis_client=redis_client.client,
        )
        app.state.authentication_provider = authentication_provider

        document_collection_catalog_client = DocumentCollectionCatalogClient(
            http_client=http_client,
        )
        app.state.document_collection_catalog_client = document_collection_catalog_client

        chat_membership_provider = ChatMembershipProvider(
            http_client=http_client,
        )
        app.state.chat_membership_provider = chat_membership_provider

        document_repository: DocumentRepository = DocumentRepository()
        app.state.document_repository = document_repository

        fragment_repository: FragmentRepository = FragmentRepository()
        app.state.fragment_repository = fragment_repository

        embedder_factory = EmbedderFactory()
        await asyncio.to_thread(lambda: embedder_factory.embedder)
        app.state.embedder_factory = embedder_factory

        reader_factory = ReaderFactory()
        app.state.reader_factory = reader_factory

        text_cleaner_factory = TextCleanerFactory()
        _ = text_cleaner_factory.cleaner
        app.state.text_cleaner_factory = text_cleaner_factory

        text_splitter_factory = TextSplitterFactory()
        await asyncio.to_thread(lambda: text_splitter_factory.splitter)
        app.state.text_splitter_factory = text_splitter_factory

        document_query_service = DocumentQueryService(
            document_repository=document_repository,
            document_collection_catalog_client=document_collection_catalog_client,
            chat_membership_provider=chat_membership_provider,
        )
        app.state.document_query_service = document_query_service

        reranker_factory = RerankerFactory()
        app.state.reranker_factory = reranker_factory
        app.state.reranker_warmup_task = asyncio.create_task(
            _warmup_reranker(reranker_factory)
        )

        fragment_query_service = FragmentQueryService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            embedder_factory=embedder_factory,
            reranker_factory=reranker_factory,
            document_collection_catalog_client=document_collection_catalog_client,
            chat_membership_provider=chat_membership_provider,
        )
        app.state.fragment_query_service = fragment_query_service

        document_search_service = DocumentSearchService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            embedder_factory=embedder_factory,
            document_collection_catalog_client=document_collection_catalog_client,
        )
        app.state.document_search_service = document_search_service

        rabbitmq_manager = RabbitMQManager()
        await rabbitmq_manager.start()
        app.state.rabbitmq_manager = rabbitmq_manager
        cleanup_stack.append(("rabbitmq_manager", rabbitmq_manager.stop))

        outbox_lite = RedisOutboxLite(
            redis_client=redis_client.client,
            rabbitmq_manager=rabbitmq_manager,
        )
        app.state.outbox_lite = outbox_lite

        knowledge_graph_settings = KnowledgeGraphSettings()
        app.state.knowledge_graph_settings = knowledge_graph_settings

        graph_extraction_publisher = None
        if knowledge_graph_settings.enabled:
            graph_extraction_publisher = GraphExtractionPublisher(
                rabbitmq_manager=rabbitmq_manager,
                outbox_lite=outbox_lite,
            )
            app.state.graph_extraction_publisher = graph_extraction_publisher
            logger.info(
                "Knowledge graph extraction publisher was registered.",
                extra={"queue": rabbitmq_manager.settings.graph_extraction_queue},
            )

        llm_provider = LlmProvider(http_client=http_client)
        app.state.llm_provider = llm_provider

        post_process_document_processor = PostProcessDocumentProcessor(
            database_manager=database_manager,
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            llm_provider=llm_provider,
        )
        app.state.post_process_document_processor = post_process_document_processor

        post_process_fragment_processor = PostProcessFragmentProcessor(
            database_manager=database_manager,
            fragment_repository=fragment_repository,
            llm_provider=llm_provider,
        )
        app.state.post_process_fragment_processor = post_process_fragment_processor

        document_enrichment_service = DocumentEnrichmentService(
            post_process_document_processor=post_process_document_processor,
            post_process_fragment_processor=post_process_fragment_processor,
            database_manager=database_manager,
            document_repository=document_repository,
        )
        app.state.document_enrichment_service = document_enrichment_service

        document_enrichment_publisher = DocumentEnrichmentPublisher(
            rabbitmq_manager=rabbitmq_manager,
            outbox_lite=outbox_lite,
        )
        app.state.document_enrichment_publisher = document_enrichment_publisher

        document_ingestion_service = DocumentIngestionService(
            database_manager=database_manager,
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            reader_factory=reader_factory,
            text_cleaner_factory=text_cleaner_factory,
            text_splitter_factory=text_splitter_factory,
            embedder_factory=embedder_factory,
            graph_extraction_publisher=graph_extraction_publisher,
            document_enrichment_publisher=document_enrichment_publisher,
        )
        app.state.document_ingestion_service = document_ingestion_service

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

        document_enrichment_consumer = DocumentEnrichmentConsumer(
            rabbitmq_manager=rabbitmq_manager,
            document_enrichment_service=document_enrichment_service,
        )
        await document_enrichment_consumer.start()
        app.state.document_enrichment_consumer = document_enrichment_consumer

        outbox_lite_worker = OutboxLiteWorker(
            outbox=outbox_lite,
            database_manager=database_manager,
            document_repository=document_repository,
            rabbitmq_settings=rabbitmq_manager.settings,
        )
        await outbox_lite_worker.start()
        app.state.outbox_lite_worker = outbox_lite_worker
        cleanup_stack.append(("outbox_lite_worker", outbox_lite_worker.stop))

        delete_document_service = DeleteDocumentService(
            document_repository=document_repository,
            fragment_repository=fragment_repository,
            chat_membership_provider=chat_membership_provider,
        )
        app.state.delete_document_service = delete_document_service

        create_document_service = CreateDocumentService(
            document_repository=document_repository,
            document_storage=document_storage,
            rabbitmq_manager=rabbitmq_manager,
            outbox_lite=outbox_lite,
        )
        app.state.create_document_service = create_document_service

        document_download_service = DocumentDownloadService(
            document_repository=document_repository,
            document_storage=document_storage,
            document_collection_catalog_client=document_collection_catalog_client,
            chat_membership_provider=chat_membership_provider,
        )
        app.state.document_download_service = document_download_service

        if knowledge_graph_settings.enabled:
            await _wire_knowledge_graph_module(
                app=app,
                cleanup_stack=cleanup_stack,
                knowledge_graph_settings=knowledge_graph_settings,
                rabbitmq_manager=rabbitmq_manager,
                redis_client=redis_client,
                database_manager=database_manager,
                document_repository=document_repository,
                fragment_repository=fragment_repository,
                document_collection_catalog_client=document_collection_catalog_client,
                llm_provider=llm_provider,
            )
        else:
            logger.info("Knowledge graph module is disabled (KNOWLEDGE_GRAPH_ENABLED=false); skipping Neo4j bootstrap.")

        logger.info("All dependencies started successfully")
        cleanup_stack.clear()

    except Exception:
        logger.critical("Error during dependency starting up; rolling back started resources in reverse order.")
        await _rollback_partial_startup(cleanup_stack=cleanup_stack, app=app)
        raise


async def _wire_knowledge_graph_module(
        *,
        app: FastAPI,
        cleanup_stack: list[tuple[str, _CleanupFn]],
        knowledge_graph_settings: KnowledgeGraphSettings,
        rabbitmq_manager: RabbitMQManager,
        redis_client: RedisClientInterface,
        database_manager: DatabaseManager,
        document_repository: DocumentRepository,
        fragment_repository: FragmentRepository,
        document_collection_catalog_client: DocumentCollectionCatalogClient,
        llm_provider: LlmProvider,
) -> None:
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
    app.state.neo4j_manager = neo4j_manager
    cleanup_stack.append(("neo4j_manager", neo4j_manager.dispose))

    graph_entity_repository = GraphEntityRepository(neo4j_manager=neo4j_manager)
    app.state.graph_entity_repository = graph_entity_repository

    graph_relation_repository = GraphRelationRepository(
        neo4j_manager=neo4j_manager,
        max_depth=knowledge_graph_settings.query_max_neighbor_depth,
    )
    app.state.graph_relation_repository = graph_relation_repository

    graph_path_repository = GraphPathRepository(neo4j_manager=neo4j_manager)
    app.state.graph_path_repository = graph_path_repository

    graph_extraction_job_progress_store = GraphExtractionJobProgressStore(
        redis_client=redis_client.client,
        lock_ttl_seconds=knowledge_graph_settings.extraction_lock_ttl_seconds,
        snapshot_ttl_seconds=knowledge_graph_settings.extraction_snapshot_ttl_seconds,
    )
    app.state.graph_extraction_job_progress_store = graph_extraction_job_progress_store

    graph_extraction_service = GraphExtractionService(
        database_manager=database_manager,
        document_repository=document_repository,
        fragment_repository=fragment_repository,
        llm_provider=llm_provider,
        entity_repository=graph_entity_repository,
        relation_repository=graph_relation_repository,
        job_progress_store=graph_extraction_job_progress_store,
        knowledge_graph_settings=knowledge_graph_settings,
    )
    app.state.graph_extraction_service = graph_extraction_service

    graph_extraction_consumer = GraphExtractionConsumer(
        rabbitmq_manager=rabbitmq_manager,
        graph_extraction_service=graph_extraction_service,
    )
    await graph_extraction_consumer.start()
    app.state.graph_extraction_consumer = graph_extraction_consumer

    graph_query_service = GraphQueryService(
        llm_provider=llm_provider,
        entity_repository=graph_entity_repository,
        relation_repository=graph_relation_repository,
        path_repository=graph_path_repository,
        document_collection_catalog_client=document_collection_catalog_client,
        knowledge_graph_settings=knowledge_graph_settings,
    )
    app.state.graph_query_service = graph_query_service

    graph_entity_service = GraphEntityService(
        entity_repository=graph_entity_repository,
        relation_repository=graph_relation_repository,
        document_collection_catalog_client=document_collection_catalog_client,
        knowledge_graph_settings=knowledge_graph_settings,
    )
    app.state.graph_entity_service = graph_entity_service

    graph_context_service = GraphContextService(
        entity_repository=graph_entity_repository,
        relation_repository=graph_relation_repository,
        document_collection_catalog_client=document_collection_catalog_client,
        knowledge_graph_settings=knowledge_graph_settings,
    )
    app.state.graph_context_service = graph_context_service

    graph_path_service = GraphPathService(
        path_repository=graph_path_repository,
        document_collection_catalog_client=document_collection_catalog_client,
        knowledge_graph_settings=knowledge_graph_settings,
    )
    app.state.graph_path_service = graph_path_service

    graph_stats_repository = GraphStatsRepository(neo4j_manager=neo4j_manager)
    app.state.graph_stats_repository = graph_stats_repository

    graph_stats_service = GraphStatsService(
        stats_repository=graph_stats_repository,
    )
    app.state.graph_stats_service = graph_stats_service

    graph_ontology_service = GraphOntologyService()
    app.state.graph_ontology_service = graph_ontology_service

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
