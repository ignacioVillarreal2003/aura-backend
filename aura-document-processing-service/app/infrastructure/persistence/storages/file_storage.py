import logging
import os
import uuid
from pathlib import Path
from typing import BinaryIO
from fastapi import UploadFile
from minio.error import S3Error

from app.application.exceptions.api_exceptions import StorageError
from app.infrastructure.persistence.storages.interfaces.file_storage_interface import FileStorageInterface
from app.infrastructure.persistence.storages.minio_client import MinioClient

logger = logging.getLogger(__name__)


class FileStorage(FileStorageInterface):
    def __init__(self,
                 client: MinioClient):
        self.client = client.client
        self.bucket_name = "documents"
        client.ensure_bucket(self.bucket_name)

    def upload(self,
               file: UploadFile) -> str:
        file_key = f"{uuid.uuid4()}{Path(file.filename).suffix}"

        try:
            file.file.seek(0, 0)

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=file_key,
                data=file.file,
                length=os.fstat(file.file.fileno()).st_size,
                content_type=file.content_type,
            )
            logger.info("File uploaded", extra={"file_key": file_key})
            return file_key

        except S3Error:
            logger.exception("Failed uploading file to MinIO")
            raise StorageError("Error al subir archivo al almacenamiento")
        except Exception:
            logger.exception("Unexpected error uploading file")
            raise StorageError("Error inesperado al subir archivo")

    def download(self,
                 file_key: str) -> BinaryIO:
        try:
            return self.client.get_object(self.bucket_name,
                                          file_key)
        except S3Error:
            raise StorageError("Error al descargar archivo del almacenamiento")

    def delete(self,
               file_key: str):
        try:
            self.client.remove_object(self.bucket_name,
                                      file_key)
            logger.info("File deleted", extra={"file_key": file_key})
        except S3Error:
            raise StorageError("Error al eliminar archivo del almacenamiento")
