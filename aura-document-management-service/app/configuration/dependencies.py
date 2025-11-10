from functools import lru_cache
from fastapi import Depends

from app.infrastructure.messaging.publisher.document_publisher import DocumentPublisher
from app.infrastructure.messaging.publisher.interfaces.document_publisher_interface import DocumentPublisherInterface
from app.infrastructure.messaging.rabbitmq_client import RabbitmqClient
from app.infrastructure.persistence.storages.document_storage_service import DocumentStorageService
from app.infrastructure.persistence.storages.interfaces.document_storage_service_interface import DocumentStorageServiceInterface
from app.infrastructure.persistence.storages.minio_client import MinioClient


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