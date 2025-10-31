from minio import Minio
from minio.error import S3Error
from pathlib import Path
import logging
import tempfile

from app.configuration.environment_variables import environment_variables
from app.application.exceptions.exceptions import StorageError


logger = logging.getLogger(__name__)

minio_client = Minio(
    endpoint=environment_variables.minio_endpoint,
    access_key=environment_variables.minio_access_key,
    secret_key=environment_variables.minio_secret_key,
    secure=environment_variables.minio_secure
)

def download_document(object_name: str, destination_dir: Path | None = None) -> Path:
    try:
        try:
            logger.debug("Ensuring MinIO bucket exists", extra={"bucket": environment_variables.minio_bucket})
            if not minio_client.bucket_exists(environment_variables.minio_bucket):
                minio_client.make_bucket(environment_variables.minio_bucket)
                logger.info("Created MinIO bucket", extra={"bucket": environment_variables.minio_bucket})
        except S3Error as e:
            logger.exception("Failed ensuring MinIO bucket exists")
            raise StorageError("Failed to ensure storage bucket exists") from e

        if destination_dir is None:
            destination_dir = Path(tempfile.gettempdir())
        destination_dir.mkdir(parents=True, exist_ok=True)

        local_path = destination_dir / object_name
        local_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Downloading object from MinIO", extra={"bucket": environment_variables.minio_bucket, "object": object_name})
        response = minio_client.get_object(
            bucket_name=environment_variables.minio_bucket,
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