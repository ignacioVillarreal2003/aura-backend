import logging
import uuid
from pathlib import Path
from typing import BinaryIO
from fastapi import UploadFile

from app.application.exceptions.exceptions import StorageError
from app.infrastructure.persistence.storages.interfaces.document_storage_service_interface import DocumentStorageServiceInterface
from app.infrastructure.persistence.storages.minio_client import MinioClient


logger = logging.getLogger(__name__)


class DocumentStorageService(DocumentStorageServiceInterface):
    def __init__(self, minio_client: MinioClient):
        self.minio_client = minio_client

    def upload_document(self,
                              file: UploadFile) -> str:
        file_key = f"{uuid.uuid4()}{Path(file.filename).suffix}"

        try:
            self.minio_client.ensure_bucket_exists()

            self.minio_client.put_object(
                object_name=file_key,
                data=file.file,
                length=file.size,
                content_type=file.content_type,
            )

            logger.info(
                "Document uploaded successfully",
                extra={
                    "file_key": file_key,
                    "original_filename": file.filename,
                    "content_type": file.content_type
                }
            )

            return file_key

        except StorageError:
            raise
        except Exception as e:
            logger.exception("Unexpected error uploading document")
            raise StorageError("Failed to upload document to storage") from e

    def download_document(self, file_key: str) -> BinaryIO:
        try:
            logger.info("Downloading document", extra={"file_key": file_key})

            response = self.minio_client.get_object(file_key)

            logger.info("Document downloaded successfully", extra={"file_key": file_key})

            return response

        except StorageError:
            raise
        except Exception as e:
            logger.exception("Unexpected error downloading document")
            raise StorageError("Failed to download document from storage") from e

    def delete_document(self,
                              file_key: str) -> None:
        try:
            logger.info("Deleting document", extra={"file_key": file_key})

            self.minio_client.delete_object(file_key)

            logger.info("Document deleted successfully", extra={"file_key": file_key})

        except StorageError:
            raise
        except Exception as e:
            logger.exception("Unexpected error deleting document")
            raise StorageError("Failed to delete document from storage") from e

    def document_exists(self, file_key: str) -> bool:
        try:
            return self.minio_client.object_exists(file_key)
        except Exception as e:
            logger.exception("Error checking if document exists")
            raise StorageError("Failed to check document existence") from e