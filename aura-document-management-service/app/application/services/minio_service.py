from minio import Minio
from minio.error import S3Error
from pathlib import Path
import uuid
import logging

from app.configuration.environment_variables import environment_variables
from app.application.exceptions.exceptions import StorageError


logger = logging.getLogger(__name__)

minio_client = Minio(
    endpoint=environment_variables.minio_endpoint,
    access_key=environment_variables.minio_access_key,
    secret_key=environment_variables.minio_secret_key,
    secure=environment_variables.minio_secure
)

async def upload_document(file) -> str:
    file_key = f"{uuid.uuid4()}{Path(file.filename).suffix}"

    try:
        try:
            logger.debug("Ensuring MinIO bucket exists", extra={"bucket": environment_variables.minio_bucket})
            if not minio_client.bucket_exists(environment_variables.minio_bucket):
                minio_client.make_bucket(environment_variables.minio_bucket)
                logger.info("Created MinIO bucket", extra={"bucket": environment_variables.minio_bucket})
        except S3Error as e:
            logger.exception("Failed ensuring MinIO bucket exists")
            raise StorageError("Failed to ensure storage bucket exists") from e

        logger.info("Uploading object to MinIO", extra={"bucket": environment_variables.minio_bucket, "object": file_key})
        minio_client.put_object(
            bucket_name=environment_variables.minio_bucket,
            object_name=file_key,
            data=file.file,
            length=file.size,
            content_type=file.content_type
        )
        logger.info("Uploaded object to MinIO", extra={"object": file_key})
        return file_key
    except S3Error as e:
        logger.exception("Failed to upload file to MinIO")
        raise StorageError("Failed to upload file to storage") from e
