import logging
import uuid
import os
from pathlib import Path
from typing import BinaryIO
from fastapi import UploadFile
from minio.error import S3Error

from app.application.exceptions.exceptions import StorageError
from app.infrastructure.persistence.storages.minio_client import MinioClient


logger = logging.getLogger(__name__)


class FileStorageRepository:
    def __init__(self, client: MinioClient):
        self.client = client.client
        self.bucket_name = "documents"
        self.client_wrapper = client
        self.client_wrapper.ensure_bucket(self.bucket_name)

    def upload(self, file: UploadFile, local_path: Path) -> str:
        file_key = f"{uuid.uuid4()}{Path(file.filename).suffix}"
        file_size = os.path.getsize(local_path)

        try:
            with open(local_path, "rb") as f:
                self.client.put_object(
                    bucket_name=self.bucket_name,
                    object_name=file_key,
                    data=f,
                    length=file_size,
                    content_type=file.content_type,
                )

            logger.info(f"File uploaded: {file_key}")
            return file_key

        except S3Error as e:
            logger.exception("Failed uploading file to MinIO")
            raise StorageError("Failed uploading file to storage") from e
        except Exception as e:
            logger.exception("Unexpected error uploading file")
            raise StorageError("Unexpected error uploading file") from e

    def download(self, file_key: str) -> BinaryIO:
        try:
            return self.client.get_object(self.bucket_name, file_key)
        except S3Error:
            raise StorageError("Failed to download file from storage")

    def delete(self, file_key: str):
        try:
            self.client.remove_object(self.bucket_name, file_key)
            logger.info(f"File deleted: {file_key}")
        except S3Error:
            raise StorageError("Failed to delete file from storage")
