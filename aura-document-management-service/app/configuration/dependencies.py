from functools import lru_cache
from typing import Generator
from fastapi import Depends
from sqlalchemy.orm.session import Session

from app.application.services.document_service import DocumentService
from app.application.services.interfaces.document_service_interface import DocumentServiceInterface
from app.infrastructure.messaging.publisher.document_publisher import DocumentPublisher
from app.infrastructure.messaging.publisher.interfaces.document_publisher_interface import DocumentPublisherInterface
from app.infrastructure.messaging.rabbitmq_client import RabbitmqClient
from app.infrastructure.persistence.repositories.database_client import DatabaseClient
from app.infrastructure.persistence.repositories.document_repository import DocumentRepository
from app.infrastructure.persistence.repositories.interfaces.document_repository_interface import DocumentRepositoryInterface
from app.infrastructure.persistence.storages.document_storage_service import DocumentStorageService
from app.infrastructure.persistence.storages.interfaces.document_storage_service_interface import DocumentStorageServiceInterface
from app.infrastructure.persistence.storages.minio_client import MinioClient


@lru_cache()
def get_database_client() -> DatabaseClient:
    return DatabaseClient()


def get_db_session(db_client: DatabaseClient = Depends(get_database_client)) -> Generator[Session, None, None]:
    yield from db_client.get_session()

@lru_cache()
def get_rabbitmq_client() -> RabbitmqClient:
    return RabbitmqClient()

def get_document_publisher(rabbitmq_client: RabbitmqClient = Depends(get_rabbitmq_client)) -> DocumentPublisherInterface:
    return DocumentPublisher(rabbitmq_client)

@lru_cache()
def get_minio_client() -> MinioClient:
    return MinioClient()

def get_document_storage_service(minio_client: MinioClient = Depends(get_minio_client)) -> DocumentStorageServiceInterface:
    return DocumentStorageService(minio_client)

def get_document_repository() -> DocumentRepositoryInterface:
    return DocumentRepository()

def get_document_service(
    document_repository: DocumentRepositoryInterface = Depends(get_document_repository),
    document_publisher: DocumentPublisherInterface = Depends(get_document_publisher),
    document_storage_service: DocumentStorageServiceInterface = Depends(get_document_storage_service),
) -> DocumentServiceInterface:
    return DocumentService(
        document_repository=document_repository,
        document_publisher=document_publisher,
        document_storage_service=document_storage_service,
    )