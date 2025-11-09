import logging
import uuid
from pathlib import Path
from minio import Minio
from minio.error import S3Error

from app.application.services.interfaces.storage_service_interface import StorageServiceInterface
from app.configuration.environment_variables import environment_variables
from app.application.exceptions.exceptions import StorageError


logger = logging.getLogger(__name__)


class MinioStorageService(StorageServiceInterface):
    def __init__(
        self,
        endpoint: str = environment_variables.minio_endpoint,
        access_key: str = environment_variables.minio_access_key,
        secret_key: str = environment_variables.minio_secret_key,
        bucket_name: str = environment_variables.minio_bucket,
        secure: bool = environment_variables.minio_secure,
    ) -> None:
        self.bucket_name = bucket_name
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

    async def upload_document(self, file) -> str:
        file_key = f"{uuid.uuid4()}{Path(file.filename).suffix}"

        try:
            await self._ensure_bucket_exists()

            logger.info(
                "Uploading object to MinIO",
                extra={"bucket": self.bucket_name, "object": file_key},
            )

            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=file_key,
                data=file.file,
                length=file.size,
                content_type=file.content_type,
            )

            logger.info("Uploaded object to MinIO", extra={"object": file_key})
            return file_key

        except S3Error as e:
            logger.exception("Failed to upload file to MinIO")
            raise StorageError("Failed to upload file to storage") from e

    async def _ensure_bucket_exists(self) -> None:
        try:
            logger.debug("Checking if MinIO bucket exists", extra={"bucket": self.bucket_name})
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info("Created MinIO bucket", extra={"bucket": self.bucket_name})
        except S3Error as e:
            logger.exception("Failed ensuring MinIO bucket exists")
            raise StorageError("Failed to ensure storage bucket exists") from e