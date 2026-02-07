import logging
import os
import uuid
from pathlib import Path
from typing import BinaryIO, Optional
from fastapi import UploadFile
from minio.error import S3Error

from app.infrastructure.persistence.storages.document_storage.document_storage_configuration import (
    DocumentStorageConfiguration
)
from app.infrastructure.persistence.storages.document_storage.exceptions.document_storage_exception import (
    DocumentStorageError,
    DocumentUploadError,
    DocumentDownloadError,
    DocumentDeleteError
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)
from app.infrastructure.persistence.storages.minio_client.interfaces.minio_client_interface import MinioClientInterface

logger = logging.getLogger(__name__)


class DocumentStorage(DocumentStorageInterface):
    def __init__(
            self,
            minio_client: MinioClientInterface,
            document_storage_configuration: DocumentStorageConfiguration
    ):
        self._minio_client = minio_client.client
        self._document_storage_configuration = document_storage_configuration
        self._bucket_name = document_storage_configuration.bucket_name

        self._ensure_bucket()

        logger.info("DocumentStorage initialized successfully")

    @classmethod
    def create(
            cls,
            minio_client: MinioClientInterface,
            bucket_name: Optional[str] = None
    ) -> "DocumentStorage":
        config_kwargs = {}

        if bucket_name is not None:
            config_kwargs['bucket_name'] = bucket_name

        document_storage_configuration = DocumentStorageConfiguration(**config_kwargs)

        return cls(
            minio_client=minio_client,
            document_storage_configuration=document_storage_configuration
        )

    def _ensure_bucket(
            self
    ) -> None:
        try:
            if not self._minio_client.bucket_exists(bucket_name=self._bucket_name):
                self._minio_client.make_bucket(self._bucket_name)
                logger.info("Bucket created successfully")
            else:
                logger.debug("Bucket already exists")

        except S3Error as e:
            logger.error(
                "S3Error ensuring bucket",
                extra={
                    "error_code": e.code,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise DocumentStorageError(f"Failed to ensure bucket {self._bucket_name}: {e.code}") from e
        except Exception as e:
            logger.exception("Unexpected error ensuring bucket")
            raise DocumentStorageError(f"Failed to ensure bucket {self._bucket_name}") from e

    def upload_document(
            self,
            document: UploadFile
    ) -> str:
        file_key = f"{uuid.uuid4()}{Path(document.filename).suffix}"

        try:
            document.file.seek(0, 0)

            self._minio_client.put_object(
                bucket_name=self._bucket_name,
                object_name=file_key,
                data=document.file,
                length=os.fstat(document.file.fileno()).st_size,
                content_type=document.content_type,
            )

            logger.info("File uploaded successfully")

            return file_key

        except S3Error as e:
            logger.error(
                "S3Error uploading file",
                extra={
                    "error_code": e.code,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise DocumentUploadError(f"Error al subir archivo al almacenamiento: {e.code}") from e
        except Exception as e:
            logger.exception("Unexpected error uploading file")
            raise DocumentUploadError("Error inesperado al subir archivo") from e

    def download_document(
            self,
            document_path: str
    ) -> BinaryIO:
        try:
            response = self._minio_client.get_object(
                bucket_name=self._bucket_name,
                object_name=document_path
            )

            logger.info("File downloaded successfully")

            return response

        except S3Error as e:
            logger.error(
                "S3Error downloading file",
                extra={
                    "error_code": e.code,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise DocumentDownloadError(f"Error al descargar archivo del almacenamiento: {e.code}") from e
        except Exception as e:
            logger.exception("Unexpected error downloading file")
            raise DocumentDownloadError("Error inesperado al descargar archivo") from e

    def delete_document(
            self,
            document_path: str
    ) -> None:
        try:
            self._minio_client.remove_object(
                bucket_name=self._bucket_name,
                object_name=document_path
            )

            logger.info("File deleted successfully")

        except S3Error as e:
            logger.error(
                "S3Error deleting file",
                extra={
                    "error_code": e.code,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise DocumentDeleteError(f"Error al eliminar archivo del almacenamiento: {e.code}") from e
        except Exception as e:
            logger.exception("Unexpected error deleting file")
            raise DocumentDeleteError("Error inesperado al eliminar archivo") from e
