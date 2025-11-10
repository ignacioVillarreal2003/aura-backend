import logging
import threading
from typing import Optional
from minio import Minio
from minio.error import S3Error


from app.configuration.environment_variables import environment_variables
from app.application.exceptions.exceptions import StorageError


logger = logging.getLogger(__name__)


class MinioClient:
    _instance: Optional['MinioClient'] = None
    _lock: threading.Lock = threading.Lock()
    _initialized: bool = False

    def __new__(cls) -> 'MinioClient':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            self.bucket_name = environment_variables.minio_bucket
            self._connect()
            self._initialized = True

    def _connect(self) -> None:
        try:
            self.client = Minio(
                endpoint=environment_variables.minio_endpoint,
                access_key=environment_variables.minio_access_key,
                secret_key=environment_variables.minio_secret_key,
                secure=environment_variables.minio_secure,
            )

            logger.info(
                "MinIO client initialized successfully",
                extra={
                    "endpoint": environment_variables.minio_endpoint,
                    "bucket": self.bucket_name
                }
            )

        except Exception as e:
            logger.exception("Failed to initialize MinIO client")
            raise StorageError("Failed to initialize MinIO client") from e

    def ensure_bucket_exists(self) -> None:
        try:
            logger.debug(
                "Checking if MinIO bucket exists",
                extra={"bucket": self.bucket_name}
            )

            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(
                    "Created MinIO bucket",
                    extra={"bucket": self.bucket_name}
                )
            else:
                logger.debug(
                    "MinIO bucket already exists",
                    extra={"bucket": self.bucket_name}
                )

        except S3Error as e:
            logger.exception("Failed ensuring MinIO bucket exists")
            raise StorageError("Failed to ensure storage bucket exists") from e

    def put_object(self,
                   object_name: str,
                   data,
                   length: int,
                   content_type: str) -> None:
        try:
            logger.info(
                "Uploading object to MinIO",
                extra={
                    "bucket": self.bucket_name,
                    "object_name": object_name,
                    "content_type": content_type,
                    "size_bytes": length
                }
            )

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=data,
                length=length,
                content_type=content_type,
            )

            logger.info(
                "Uploaded object to MinIO successfully",
                extra={"bucket": self.bucket_name, "object_name": object_name}
            )

        except S3Error as e:
            logger.exception(
                "Failed to upload object to MinIO",
                extra={"object_name": object_name}
            )
            raise StorageError("Failed to upload file to storage") from e

    def get_object(self,
                   object_name: str):
        try:
            logger.info(
                "Downloading object from MinIO",
                extra={"bucket": self.bucket_name, "object_name": object_name}
            )

            response = self.client.get_object(self.bucket_name, object_name)

            logger.info(
                "Downloaded object from MinIO successfully",
                extra={"bucket": self.bucket_name, "object_name": object_name}
            )

            return response

        except S3Error as e:
            logger.exception(
                "Failed to download object from MinIO",
                extra={"object_name": object_name}
            )
            raise StorageError("Failed to download file from storage") from e

    def delete_object(self,
                      object_name: str,) -> None:
        try:
            logger.info(
                "Deleting object from MinIO",
                extra={"bucket": self.bucket_name, "object_name": object_name}
            )

            self.client.remove_object(self.bucket_name, object_name)

            logger.info(
                "Deleted object from MinIO successfully",
                extra={"bucket": self.bucket_name, "object_name": object_name}
            )

        except S3Error as e:
            logger.exception(
                "Failed to delete object from MinIO",
                extra={"object_name": object_name}
            )
            raise StorageError("Failed to delete file from storage") from e

    def object_exists(self,
                      object_name: str) -> bool:
        try:
            self.client.stat_object(self.bucket_name, object_name)
            return True
        except S3Error:
            return False