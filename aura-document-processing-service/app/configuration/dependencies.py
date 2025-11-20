from functools import lru_cache
from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.services.document_service import DocumentService
from app.application.services.ingestion_service import IngestionService
from app.application.services.interfaces.document_service_interface import DocumentServiceInterface
from app.application.services.interfaces.ingestion_service_interface import IngestionServiceInterface
from app.application.services.interfaces.retrival_service_interface import RetrivalServiceInterface
from app.application.services.retrival_service import RetrievalService
from app.infrastructure.persistence.repositories.database_client import DatabaseClient
from app.infrastructure.persistence.repositories.document_repository import DocumentRepository
from app.infrastructure.persistence.repositories.fragment_repository import FragmentRepository
from app.infrastructure.persistence.repositories.interfaces.document_repository_interface import \
    DocumentRepositoryInterface
from app.infrastructure.persistence.repositories.interfaces.fragment_repository_interface import \
    FragmentRepositoryInterface
from app.infrastructure.persistence.storages.file_storage import FileStorage
from app.infrastructure.persistence.storages.interfaces.file_storage_interface import FileStorageInterface
from app.infrastructure.persistence.storages.minio_client import MinioClient


@lru_cache()
def get_minio_client() -> MinioClient:
    return MinioClient()


def get_file_storage() -> FileStorageInterface:
    return FileStorage(get_minio_client())


@lru_cache()
def get_database_client() -> DatabaseClient:
    return DatabaseClient()


def get_db_session(db_client: DatabaseClient = Depends(get_database_client)) -> Generator[Session, None, None]:
    yield from db_client.get_session()


def get_document_repository() -> DocumentRepositoryInterface:
    return DocumentRepository()


def get_fragment_repository() -> FragmentRepositoryInterface:
    return FragmentRepository()


def get_ingestion_service(document_repository: DocumentRepositoryInterface = Depends(get_document_repository),
                          fragment_repository: FragmentRepositoryInterface = Depends(get_fragment_repository)) -> IngestionServiceInterface:
    return IngestionService(document_repository,
                            fragment_repository)


def get_retrieval_service(fragment_repository: FragmentRepositoryInterface = Depends(get_fragment_repository)) -> RetrivalServiceInterface:
    return RetrievalService(fragment_repository)


def get_document_service(document_repository: DocumentRepositoryInterface = Depends(get_document_repository),
                         file_storage: FileStorageInterface = Depends(get_file_storage),
                         ingestion_service: IngestionServiceInterface = Depends(get_ingestion_service)) -> DocumentServiceInterface:
    return DocumentService(
        document_repository=document_repository,
        file_storage=file_storage,
        ingestion_service=ingestion_service
    )