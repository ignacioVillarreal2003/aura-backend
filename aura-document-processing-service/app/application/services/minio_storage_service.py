from pathlib import Path
import logging
import tempfile
from minio import Minio
from minio.error import S3Error

from app.application.services.interfaces.storage_service_interface import StorageServiceInterface
from app.configuration.environment_variables import environment_variables
from app.application.exceptions.exceptions import StorageError


logger = logging.getLogger(__name__)


class MinioStorageService(StorageServiceInterface):
    def __init__(self,
                 endpoint: str = environment_variables.minio_endpoint,
                 access_key: str = environment_variables.minio_access_key,
                 secret_key: str = environment_variables.minio_secret_key,
                 bucket_name: str = environment_variables.minio_bucket,
                 secure: bool = environment_variables.minio_secure) -> None:
        self.bucket_name = bucket_name
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

    def download_document(self,
                          object_name: str,
                          destination_dir: Path | None = None) -> Path:
        try:
            self._ensure_bucket_exists()

            if destination_dir is None:
                destination_dir = Path(tempfile.gettempdir())
            destination_dir.mkdir(parents=True, exist_ok=True)

            local_path = destination_dir / object_name
            local_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(
                "Downloading object from MinIO",
                extra={"bucket": self.bucket_name, "object": object_name},
            )

            response = self.client.get_object(
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            try:
                with open(local_path, "wb") as f:
                    for data in response.stream(32 * 1024):
                        f.write(data)
            finally:
                response.close()
                response.release_conn()

            logger.info("Downloaded object from MinIO", extra={"object": str(local_path)})
            return local_path

        except S3Error as e:
            logger.exception("Failed to download file from MinIO")
            raise StorageError("Failed to download file from storage") from e

    def _ensure_bucket_exists(self) -> None:
        try:
            logger.debug("Checking if MinIO bucket exists", extra={"bucket": self.bucket_name})
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info("Created MinIO bucket", extra={"bucket": self.bucket_name})
        except S3Error as e:
            logger.exception("Failed ensuring MinIO bucket exists")
            raise StorageError("Failed to ensure storage bucket exists") from e