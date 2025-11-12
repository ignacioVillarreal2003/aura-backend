import logging
import threading
from typing import Optional
from minio import Minio
from minio.error import S3Error

from app.configuration.environment_variables import environment_variables
from app.application.exceptions.exceptions import StorageError


logger = logging.getLogger(__name__)


class MinioClient:
    _instance: Optional["MinioClient"] = None
    _lock = threading.Lock()
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        try:
            self.client = Minio(
                endpoint=environment_variables.minio_endpoint,
                access_key=environment_variables.minio_access_key,
                secret_key=environment_variables.minio_secret_key,
                secure=environment_variables.minio_secure,
            )
            logger.info("MinIO client initialized", extra={
                "endpoint": environment_variables.minio_endpoint
            })
            self._initialized = True
        except Exception as e:
            logger.exception("Failed to initialize MinIO client")
            raise StorageError("Failed to initialize MinIO connection") from e

    def ensure_bucket(self, bucket_name: str):
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                logger.info(f"Bucket created: {bucket_name}")
        except S3Error as e:
            logger.exception(f"Failed ensuring bucket: {bucket_name}")
            raise StorageError(f"Failed to ensure bucket {bucket_name}") from e