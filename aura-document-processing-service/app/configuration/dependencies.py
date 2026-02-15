import logging
from fastapi import FastAPI

from app.application.services.document_creation_service.document_creation_service_factory import (
    create_document_creation_service
)
from app.application.services.document_deletion_service.document_deletion_service_factory import (
    create_document_deletion_service
)
from app.application.services.document_ingestion_service.document_ingestion_service_factory import (
    create_document_ingestion_service
)
from app.application.services.document_query_service.document_query_service_factory import create_document_query_service
from app.application.services.document_retrieve_service.document_retrieve_service_factory import (
    create_document_retrieve_service
)
from app.configuration.environment_variables import environment_variables
from app.infrastructure.http_client.http_client_factory import create_http_client
from app.infrastructure.persistence.database.database_manager.database_manager_factory import create_database_manager
from app.infrastructure.persistence.storages.document_storage.document_storage_factory import create_document_storage
from app.infrastructure.persistence.storages.minio_manager.minio_manager_factory import create_minio_manager

logger = logging.getLogger(__name__)


async def startup_dependencies(
        app: FastAPI
) -> None:
    try:
        logger.info("Starting up dependencies")

        database_manager = create_database_manager(
            user=environment_variables.database_user,
            password=environment_variables.database_password,
            host=environment_variables.database_host,
            port=environment_variables.database_port,
            name=environment_variables.database_name,
            database_driver=environment_variables.database_driver
        )
        await database_manager.initialize()
        app.state.db_manager = database_manager

        minio_manager = create_minio_manager(
            minio_endpoint=environment_variables.minio_endpoint,
            minio_access_key=environment_variables.minio_access_key,
            minio_secret_key=environment_variables.minio_secret_key
        )
        await minio_manager.start()
        app.state.minio_manager = minio_manager

        http_client = create_http_client()
        await http_client.start()
        app.state.http_client = http_client

        document_storage = create_document_storage(
            minio_manager=minio_manager
        )
        await document_storage.start()
        app.state.document_storage = document_storage

        document_ingestion_service = create_document_ingestion_service(
            database_manager=database_manager
        )
        app.state.document_ingestion_service = document_ingestion_service

        document_creation_service = create_document_creation_service(
            document_storage=document_storage,
            document_ingestion_service=document_ingestion_service
        )
        app.state.document_creation_service = document_creation_service

        document_deletion_service = create_document_deletion_service(
            document_storage=document_storage
        )
        app.state.document_deletion_service = document_deletion_service

        document_query_service = create_document_query_service()
        app.state.document_query_service = document_query_service

        document_retrieve_service = create_document_retrieve_service()
        app.state.document_retrieve_service = document_retrieve_service

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
