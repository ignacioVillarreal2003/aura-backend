import logging

from app.application.processors.embedders.embedder_factory import EmbedderFactory
from app.application.processors.readers.reader_factory import ReaderFactory
from app.application.processors.text_cleaners.text_cleaner_factory import TextCleanerFactory
from app.application.processors.text_splitters.text_splitter_factory import TextSplitterFactory
from app.application.services.document_context_service.document_context_service import DocumentContextService
from app.application.services.document_context_service.interfaces.document_context_service_interface import (
    DocumentContextServiceInterface
)
from app.application.services.document_creation_service.document_creation_service import DocumentCreationService
from app.application.services.document_creation_service.interfaces.document_creation_service_interface import (
    DocumentCreationServiceInterface
)
from app.application.services.document_ingestion_service.document_ingestion_service import DocumentIngestionService
from app.application.services.document_ingestion_service.interfaces.document_ingestion_service_interface import (
    DocumentIngestionServiceInterface
)
from app.infrastructure.persistence.repositories.database_client.database_client_factory import (
    get_global_database_client,
    shutdown_global_database_client
)
from app.infrastructure.persistence.repositories.database_client.interfaces.database_client_interface import (
    DatabaseClientInterface
)
from app.infrastructure.persistence.repositories.document_repository.document_repository import DocumentRepository
from app.infrastructure.persistence.repositories.document_repository.interfaces.document_repository_interface import (
    DocumentRepositoryInterface
)
from app.infrastructure.persistence.repositories.fragment_repository.fragment_repository import FragmentRepository
from app.infrastructure.persistence.repositories.fragment_repository.interfaces.fragment_repository_interface import (
    FragmentRepositoryInterface
)
from app.infrastructure.persistence.storages.document_storage.document_storage import DocumentStorage
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)
from app.configuration.environment_variables import environment_variables
from app.infrastructure.persistence.storages.minio_client.interfaces.minio_client_interface import MinioClientInterface
from app.infrastructure.persistence.storages.minio_client.minio_client_factory import (
    get_global_minio_client,
    shutdown_global_minio_client
)

logger = logging.getLogger(__name__)


async def get_database_client() -> DatabaseClientInterface:
    return await get_global_database_client(
        db_driver=environment_variables.db_driver,
        db_user=environment_variables.db_user,
        db_password=environment_variables.db_password,
        db_host=environment_variables.db_host,
        db_port=environment_variables.db_port,
        db_name=environment_variables.db_name
    )


async def get_database_session():
    database_client = await get_database_client()
    return database_client.get_session()


def get_document_repository() -> DocumentRepositoryInterface:
    return DocumentRepository()


def get_fragment_repository() -> FragmentRepositoryInterface:
    return FragmentRepository()


async def get_minio_client() -> MinioClientInterface:
    return await get_global_minio_client(
        minio_endpoint=environment_variables.minio_endpoint,
        minio_access_key=environment_variables.minio_access_key,
        minio_secret_key=environment_variables.minio_secret_key,
        minio_secure=environment_variables.minio_secure
    )


async def get_document_storage() -> DocumentStorageInterface:
    minio_client = await get_minio_client()
    return DocumentStorage.create(
        minio_client=minio_client
    )


def get_reader_factory() -> ReaderFactory:
    return ReaderFactory()


def get_text_cleaner_factory() -> TextCleanerFactory:
    return TextCleanerFactory()


def get_text_splitter_factory() -> TextSplitterFactory:
    return TextSplitterFactory()


def get_embedder_factory() -> EmbedderFactory:
    return EmbedderFactory()


def get_document_ingestion_service() -> DocumentIngestionServiceInterface:
    document_repository = get_document_repository()
    fragment_repository = get_fragment_repository()
    reader_factory = get_reader_factory()
    text_cleaner_factory = get_text_cleaner_factory()
    text_splitter_factory = get_text_splitter_factory()
    embedder_factory = get_embedder_factory()
    return DocumentIngestionService.create(
        document_repository=document_repository,
        fragment_repository=fragment_repository,
        reader_factory=reader_factory,
        text_cleaner_factory=text_cleaner_factory,
        text_splitter_factory=text_splitter_factory,
        embedder_factory=embedder_factory,
        text_cleaner_type=environment_variables.text_cleaner_type,
        text_splitter_type=environment_variables.text_splitter_type,
        embedder_type=environment_variables.embedder_type
    )


async def get_document_creation_service() -> DocumentCreationServiceInterface:
    document_repository = get_document_repository()
    document_storage = await get_document_storage()
    document_ingestion_service = get_document_ingestion_service()
    return DocumentCreationService.create(
        document_repository=document_repository,
        document_storage=document_storage,
        document_ingestion_service=document_ingestion_service
    )


def get_document_context_service() -> DocumentContextServiceInterface:
    fragment_repository = get_fragment_repository()
    embedder_factory = get_embedder_factory()
    return DocumentContextService.create(
        fragment_repository=fragment_repository,
        embedder_factory=embedder_factory,
        embedder_type=environment_variables.embedder_type
    )


async def startup_dependencies() -> None:
    try:
        logger.info("Starting up application dependencies")

        database_client = await get_database_client()
        if not database_client.is_started:
            await database_client.start()

        minio_client = await get_minio_client()
        if not minio_client.is_started:
            await minio_client.start()

        logger.info("All dependencies started successfully")

    except Exception:
        logger.critical("Failed to start dependencies")
        raise


async def shutdown_dependencies() -> None:
    try:
        logger.info("Shutting down application dependencies")

        await shutdown_global_database_client()
        await shutdown_global_minio_client()

        logger.info("All dependencies shut down successfully")

    except Exception:
        logger.error("Error during dependency shutdown")
