from functools import lru_cache
from typing import Generator
from fastapi import Depends
from sqlalchemy.orm import Session

from app.application.services.document_service import DocumentService
from app.application.services.ingestion_service import IngestionService
from app.infrastructure.persistence.repositories.database_client import DatabaseClient
from app.infrastructure.persistence.repositories.document_repository import DocumentRepository
from app.infrastructure.persistence.repositories.fragment_repository import FragmentRepository
from app.infrastructure.persistence.storages.file_storage_repository import FileStorageRepository
from app.infrastructure.persistence.storages.minio_client import MinioClient


@lru_cache()
def get_database_client() -> DatabaseClient:
    return DatabaseClient()


def get_db_session(db_client: DatabaseClient = Depends(get_database_client)) -> Generator[Session, None, None]:
    yield from db_client.get_session()


def get_document_repository() -> DocumentRepository:
    return DocumentRepository()


def get_fragment_repository() -> FragmentRepository:
    return FragmentRepository()


@lru_cache()
def get_minio_client() -> MinioClient:
    return MinioClient()

def get_file_storage_repository() -> FileStorageRepository:
    return FileStorageRepository(get_minio_client())

@lru_cache()
def get_ingestion_service(
    document_repository: DocumentRepository = Depends(get_document_repository),
    fragment_repository: FragmentRepository = Depends(get_fragment_repository)
) -> IngestionService:
    return IngestionService(document_repository, fragment_repository)


def get_document_service(
    document_repository: DocumentRepository = Depends(get_document_repository),
    file_storage_repository: FileStorageRepository = Depends(get_file_storage_repository),
    ingestion_service: IngestionService = Depends(get_ingestion_service)
) -> DocumentService:
    return DocumentService(
        document_repository=document_repository,
        file_storage_repository=file_storage_repository,
        ingestion_service=ingestion_service
    )
