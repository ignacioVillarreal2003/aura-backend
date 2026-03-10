import asyncio
import logging
import threading
import time
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import urllib3
from minio import Minio
from minio.error import InvalidResponseError, S3Error
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.infrastructure.persistence.storages.minio_manager.exceptions.minio_manager_exception import (
    MinioBucketException,
    MinioConnectionException,
    MinioManagerNotInitializedException,
    MinioOperationException,
    MinioUploadException,
    MinioDownloadException,
    MinioDeleteException
)
from app.infrastructure.persistence.storages.minio_manager.interfaces.minio_manager_interface import (
    MinioManagerInterface
)
from app.infrastructure.persistence.storages.minio_manager.minio_manager_settings import (
    MinioManagerSettings
)

logger = logging.getLogger(__name__)


class MinioManager(MinioManagerInterface):
    def __init__(
            self,
            minio_manager_settings: Optional[MinioManagerSettings] = None,
    ) -> None:
        self._minio_manager_settings = minio_manager_settings or MinioManagerSettings()
        self._client: Optional[Minio] = None

        self._lifecycle_lock = asyncio.Lock()
        self._is_started: bool = False

        self._ensure_bucket_retried: Optional[Callable] = None
        self._upload_file_retried: Optional[Callable] = None
        self._upload_data_retried: Optional[Callable] = None
        self._download_file_retried: Optional[Callable] = None
        self._download_data_retried: Optional[Callable] = None
        self._delete_object_retried: Optional[Callable] = None

        self._metrics_lock = threading.Lock()
        self._operation_count: int = 0
        self._error_count: int = 0
        self._upload_count: int = 0
        self._download_count: int = 0
        self._bytes_uploaded: int = 0
        self._bytes_downloaded: int = 0

    async def start(self) -> None:
        async with self._lifecycle_lock:
            if self._is_started:
                logger.debug("MinioManager already started — skipping")
                return

            logger.info(
                "Starting MinioManager",
                extra={
                    "endpoint": self._minio_manager_settings.endpoint_safe
                }
            )

            try:
                http_client = urllib3.PoolManager(
                    timeout=urllib3.Timeout(
                        connect=self._minio_manager_settings.tcp_connect_timeout_seconds,
                        read=self._minio_manager_settings.socket_read_timeout_seconds
                    ),
                    maxsize=self._minio_manager_settings.connection_pool_size,
                    retries=False
                )

                self._client = Minio(
                    **self._minio_manager_settings.get_minio_config(),
                    http_client=http_client
                )

                s3_retry = retry(
                    stop=stop_after_attempt(self._minio_manager_settings.retry_max_attempts),
                    wait=wait_exponential(
                        multiplier=self._minio_manager_settings.retry_backoff_multiplier,
                        min=self._minio_manager_settings.retry_backoff_min_seconds,
                        max=self._minio_manager_settings.retry_backoff_max_seconds
                    ),
                    retry=retry_if_exception_type(S3Error),
                    before_sleep=before_sleep_log(
                        logger,
                        logging.WARNING
                    ),
                    reraise=True
                )

                self._ensure_bucket_retried = s3_retry(self._ensure_bucket_core)
                self._upload_file_retried = s3_retry(self._upload_file_core)
                self._upload_data_retried = s3_retry(self._upload_data_core)
                self._download_file_retried = s3_retry(self._download_file_core)
                self._download_data_retried = s3_retry(self._download_data_core)
                self._delete_object_retried = s3_retry(self._delete_object_core)

                await self._verify_connection()

                self._is_started = True
                logger.info("MinioManager started successfully")

            except S3Error as e:
                self._client = None
                logger.error(
                    "S3 error during MinioManager startup",
                    extra={
                        "error_code": e.code
                    }
                )
                raise MinioConnectionException(f"Failed to connect to MinIO: {e.code}") from e

            except Exception as e:
                self._client = None
                logger.exception("Failed to start MinioManager")
                raise MinioConnectionException("Failed to start MinIO client") from e

    async def stop(self) -> None:
        async with self._lifecycle_lock:
            if not self._is_started:
                logger.debug("MinioManager already stopped — skipping")
                return

            logger.info(
                "Stopping MinioManager",
                extra=self.get_metrics()
            )

            self._client = None
            self._ensure_bucket_retried = None
            self._upload_file_retried = None
            self._upload_data_retried = None
            self._download_file_retried = None
            self._download_data_retried = None
            self._delete_object_retried = None
            self._is_started = False

            logger.info("MinioManager stopped successfully")

    @property
    def is_started(self) -> bool:
        return self._is_started

    @property
    def client(self) -> Minio:
        if (not self._is_started
                or not self._client):
            raise MinioManagerNotInitializedException("MinioManager is not started. Call start() first.")
        return self._client

    async def ensure_bucket(
            self,
            bucket_name: str
    ) -> None:
        await self._ensure_bucket_retried(bucket_name)

    async def upload_file(
            self,
            bucket_name: str,
            object_name: str,
            file_path: str,
            content_type: Optional[str] = None,
            metadata: Optional[Dict[str, str]] = None
    ) -> None:
        await self._upload_file_retried(
            bucket_name,
            object_name,
            file_path,
            content_type,
            metadata
        )

    async def upload_data(
            self,
            bucket_name: str,
            object_name: str,
            data: bytes,
            content_type: Optional[str] = None,
            metadata: Optional[Dict[str, str]] = None
    ) -> None:
        await self._upload_data_retried(
            bucket_name,
            object_name,
            data,
            content_type,
            metadata
        )

    async def download_file(
            self,
            bucket_name: str,
            object_name: str,
            file_path: str
    ) -> None:
        await self._download_file_retried(
            bucket_name,
            object_name,
            file_path
        )

    async def download_data(
            self,
            bucket_name: str,
            object_name: str
    ) -> bytes:
        return await self._download_data_retried(
            bucket_name,
            object_name
        )

    async def delete_object(
            self,
            bucket_name: str,
            object_name: str
    ) -> None:
        await self._delete_object_retried(
            bucket_name,
            object_name
        )

    async def _ensure_bucket_core(
            self,
            bucket_name: str
    ) -> None:
        client = self.client

        try:
            exists: bool = await asyncio.to_thread(
                client.bucket_exists,
                bucket_name
            )

            if not exists:
                logger.info(
                    "Creating bucket",
                    extra={
                        "bucket": bucket_name
                    }
                )
                await asyncio.to_thread(
                    client.make_bucket,
                    bucket_name,
                    location=self._minio_manager_settings.region
                )
                logger.info(
                    "Bucket created successfully",
                    extra={
                        "bucket": bucket_name
                    }
                )
            else:
                logger.debug(
                    "Bucket already exists",
                    extra={
                        "bucket": bucket_name
                    }
                )

            self._operation_count += 1

        except S3Error as e:
            self._error_count += 1
            logger.error(
                "S3 error ensuring bucket",
                extra={
                    "bucket": bucket_name,
                    "error_code": e.code
                }
            )
            raise MinioBucketException(f"Failed to ensure bucket '{bucket_name}': {e.code}") from e

        except Exception as e:
            self._error_count += 1
            raise MinioBucketException(f"Failed to ensure bucket '{bucket_name}'") from e

    async def _upload_file_core(
            self,
            bucket_name: str,
            object_name: str,
            file_path: str,
            content_type: Optional[str],
            metadata: Optional[Dict[str, str]]
    ) -> None:
        client = self.client

        try:
            logger.debug(
                "Uploading file to MinIO",
                extra={
                    "bucket": bucket_name,
                    "object": object_name
                }
            )

            if self._minio_manager_settings.auto_create_bucket_if_missing:
                await self._ensure_bucket_core(bucket_name)

            result = await asyncio.to_thread(
                client.fput_object,
                bucket_name,
                object_name,
                file_path,
                content_type=content_type,
                metadata=metadata
            )

            file_size = Path(file_path).stat().st_size
            self._operation_count += 1
            self._upload_count += 1
            self._bytes_uploaded += file_size

            logger.info(
                "File uploaded successfully",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "size_bytes": file_size,
                    "etag": result.etag
                }
            )

        except S3Error as e:
            self._error_count += 1
            logger.error(
                "S3 error uploading file",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "error_code": e.code
                }
            )
            raise MinioUploadException(f"Failed to upload file '{object_name}': {e.code}") from e

        except Exception as e:
            self._error_count += 1
            raise MinioUploadException(f"Failed to upload file '{object_name}'") from e

    async def _upload_data_core(
            self,
            bucket_name: str,
            object_name: str,
            data: bytes,
            content_type: Optional[str],
            metadata: Optional[Dict[str, str]]
    ) -> None:
        client = self.client
        data_length = len(data)

        try:
            logger.debug(
                "Uploading data to MinIO",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "size_bytes": data_length
                }
            )

            if self._minio_manager_settings.auto_create_bucket_if_missing:
                await self._ensure_bucket_core(bucket_name)

            result = await asyncio.to_thread(
                client.put_object,
                bucket_name,
                object_name,
                BytesIO(data),
                data_length,
                content_type=content_type,
                metadata=metadata,
            )

            self._operation_count += 1
            self._upload_count += 1
            self._bytes_uploaded += data_length

            logger.info(
                "Data uploaded successfully",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "size_bytes": data_length,
                    "etag": result.etag
                }
            )

        except S3Error as e:
            self._error_count += 1
            logger.error(
                "S3 error uploading data",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "error_code": e.code
                }
            )
            raise MinioOperationException(f"Failed to upload data to '{object_name}': {e.code}") from e

        except Exception as e:
            self._error_count += 1
            raise MinioOperationException(f"Failed to upload data to '{object_name}'") from e

    async def _download_file_core(
            self,
            bucket_name: str,
            object_name: str,
            file_path: str
    ) -> None:
        client = self.client

        try:
            logger.debug(
                "Downloading file from MinIO",
                extra={
                    "bucket": bucket_name,
                    "object": object_name
                }
            )

            await asyncio.to_thread(
                client.fget_object,
                bucket_name,
                object_name,
                file_path
            )

            file_size = Path(file_path).stat().st_size
            self._operation_count += 1
            self._download_count += 1
            self._bytes_downloaded += file_size

            logger.info(
                "File downloaded successfully",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "size_bytes": file_size
                }
            )

        except S3Error as e:
            self._error_count += 1
            logger.error(
                "S3 error downloading file",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "error_code": e.code
                }
            )
            raise MinioDownloadException(f"Failed to download file '{object_name}': {e.code}") from e

        except Exception as e:
            self._error_count += 1
            raise MinioDownloadException(f"Failed to download file '{object_name}'") from e

    async def _download_data_core(
            self,
            bucket_name: str,
            object_name: str
    ) -> bytes:
        client = self.client

        try:
            logger.debug(
                "Downloading data from MinIO",
                extra={
                    "bucket": bucket_name,
                    "object": object_name
                }
            )

            def _read_response() -> bytes:
                response = client.get_object(bucket_name, object_name)
                try:
                    return response.read()
                finally:
                    response.close()
                    response.release_conn()

            data: bytes = await asyncio.to_thread(_read_response)

            self._operation_count += 1
            self._download_count += 1
            self._bytes_downloaded += len(data)

            logger.info(
                "Data downloaded successfully",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "size_bytes": len(data)
                }
            )
            return data

        except S3Error as e:
            self._error_count += 1
            logger.error(
                "S3 error downloading data",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "error_code": e.code
                }
            )
            raise MinioOperationException(f"Failed to download data from '{object_name}': {e.code}") from e

        except Exception as e:
            self._error_count += 1
            raise MinioOperationException(f"Failed to download data from '{object_name}'") from e

    async def _delete_object_core(
            self,
            bucket_name: str,
            object_name: str
    ) -> None:
        client = self.client

        try:
            logger.debug(
                "Deleting object from MinIO",
                extra={
                    "bucket": bucket_name,
                    "object": object_name
                }
            )

            await asyncio.to_thread(
                client.remove_object,
                bucket_name,
                object_name
            )

            self._operation_count += 1

            logger.info(
                "Object deleted successfully",
                extra={
                    "bucket": bucket_name,
                    "object": object_name
                }
            )

        except S3Error as e:
            self._error_count += 1
            logger.error(
                "S3 error deleting object",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "error_code": e.code
                }
            )
            raise MinioDeleteException(f"Failed to delete object '{object_name}': {e.code}") from e

        except Exception as e:
            self._error_count += 1
            raise MinioDeleteException(f"Failed to delete object '{object_name}'") from e

    async def object_exists(
            self,
            bucket_name: str,
            object_name: str
    ) -> bool:
        client = self.client

        try:
            await asyncio.to_thread(
                client.stat_object,
                bucket_name,
                object_name
            )
            self._operation_count += 1
            return True

        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            self._error_count += 1
            raise

        except Exception:
            self._error_count += 1
            raise

    async def get_presigned_url(
            self,
            bucket_name: str,
            object_name: str,
            expires: Optional[int] = None,
            method: str = "GET"
    ) -> str:
        client = self.client
        expiry_seconds = (
            expires
            if expires is not None
            else self._minio_manager_settings.presigned_url_expiry_seconds
        )

        try:
            url: str = await asyncio.to_thread(
                client.presigned_url,
                method,
                bucket_name,
                object_name,
                expires=timedelta(
                    seconds=expiry_seconds
                )
            )

            self._operation_count += 1
            return url

        except Exception as e:
            self._error_count += 1
            logger.exception(
                "Error generating presigned URL",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "method": method
                }
            )
            raise MinioOperationException(f"Failed to generate presigned URL for '{object_name}'") from e

    async def list_objects(
            self,
            bucket_name: str,
            prefix: Optional[str] = None,
            recursive: bool = False
    ) -> List[Dict[str, Any]]:
        client = self.client

        try:
            def _collect() -> List[Dict[str, Any]]:
                return [
                    {
                        "name": obj.object_name,
                        "size": obj.size,
                        "etag": obj.etag,
                        "last_modified": obj.last_modified,
                        "content_type": obj.content_type
                    }
                    for obj in client.list_objects(
                        bucket_name,
                        prefix=prefix,
                        recursive=recursive
                    )
                ]

            result = await asyncio.to_thread(_collect)

            self._operation_count += 1

            logger.debug(
                "Objects listed successfully",
                extra={
                    "bucket": bucket_name,
                    "prefix": prefix,
                    "count": len(result)
                }
            )
            return result

        except Exception as e:
            self._error_count += 1
            logger.exception(
                "Error listing objects",
                extra={
                    "bucket": bucket_name,
                    "prefix": prefix
                }
            )
            raise MinioOperationException(f"Failed to list objects in '{bucket_name}'") from e

    async def health_check(self) -> Dict[str, Any]:
        if (not self._is_started
                or not self._client):
            return {
                "status": "unhealthy",
                "started": False,
                "error": "MinIO client not started",
            }

        try:
            start_time = time.monotonic()
            await asyncio.to_thread(self._client.list_buckets)
            latency_ms = round((time.monotonic() - start_time) * 1000, 2)

            return {
                "status": "healthy",
                "started": True,
                "latency_ms": latency_ms,
                "endpoint": self._minio_manager_settings.endpoint_safe,
                "metrics": self.get_metrics()
            }

        except S3Error as e:
            logger.warning(
                "MinIO health check failed",
                extra={
                    "error_code": e.code
                }
            )
            return {
                "status": "unhealthy",
                "started": True,
                "error": f"S3 error: {e.code}"
            }

        except Exception:
            logger.warning("MinIO health check failed — see logs for details")
            return {
                "status": "unhealthy",
                "started": True,
                "error": "Health probe failed — see logs for details",
            }

    def get_metrics(self) -> Dict[str, int]:
        with self._metrics_lock:
            return {
                "operation_count": self._operation_count,
                "error_count": self._error_count,
                "upload_count": self._upload_count,
                "download_count": self._download_count,
                "bytes_uploaded": self._bytes_uploaded,
                "bytes_downloaded": self._bytes_downloaded
            }

    async def __aenter__(self) -> "MinioManager":
        await self.start()
        return self

    async def __aexit__(
            self,
            exc_type,
            exc_val,
            exc_tb
    ) -> None:
        await self.stop()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=10
        ),
        retry=retry_if_exception_type((
                S3Error,
                InvalidResponseError
        )),
        before_sleep=before_sleep_log(
            logger,
            logging.WARNING
        ),
        reraise=True
    )
    async def _verify_connection(self) -> None:
        if not self._client:
            raise RuntimeError("Client not initialised before connection verification")

        logger.info("Verifying MinIO connection")
        await asyncio.to_thread(self._client.list_buckets)
        logger.info("MinIO connection verified successfully")
