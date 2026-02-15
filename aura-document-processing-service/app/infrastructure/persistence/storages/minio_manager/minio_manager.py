import logging
import time
import asyncio
from typing import Optional, Dict, Any, List
from io import BytesIO
from datetime import timedelta
from asyncio import Lock
from minio import Minio
from minio.error import S3Error, InvalidResponseError
from urllib3 import Timeout
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential, before_sleep_log

from app.infrastructure.persistence.storages.minio_manager.minio_manager_settings import (
    MinioManagerSettings
)
from app.infrastructure.persistence.storages.minio_manager.exceptions.minio_manager_exception import (
    MinioConnectionException,
    MinioBucketException,
    MinioOperationException, MinioManagerNotInitializedException
)
from app.infrastructure.persistence.storages.minio_manager.interfaces.minio_manager_interface import (
    MinioManagerInterface
)

logger = logging.getLogger(__name__)


class MinioManager(MinioManagerInterface):
    def __init__(
            self,
            minio_manager_settings: MinioManagerSettings
    ) -> None:
        self._minio_manager_settings = minio_manager_settings
        self._client: Optional[Minio] = None
        self._lock = Lock()
        self._is_started = False

        self._operation_count = 0
        self._error_count = 0
        self._upload_count = 0
        self._download_count = 0
        self._bytes_uploaded = 0
        self._bytes_downloaded = 0
        self._last_health_check: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
            cls,
            endpoint: str,
            access_key: str,
            secret_key: str,
            **config_kwargs
    ) -> "MinioManager":
        minio_manager_settings = MinioManagerSettings(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            **config_kwargs
        )

        return cls(
            minio_manager_settings=minio_manager_settings
        )

    async def start(
            self
    ) -> None:
        async with self._lock:
            if self._is_started:
                logger.debug("MinioClient already started")
                return

            logger.info(
                "Starting MinioClient",
                extra={
                    "endpoint": self._minio_manager_settings.endpoint_safe
                }
            )

            try:
                timeout = Timeout(
                    connect=self._minio_manager_settings.connect_timeout,
                    read=self._minio_manager_settings.read_timeout,
                )

                self._client = Minio(
                    endpoint=self._minio_manager_settings.endpoint,
                    access_key=self._minio_manager_settings.access_key,
                    secret_key=self._minio_manager_settings.secret_key.get_secret_value(),
                    secure=self._minio_manager_settings.secure,
                    region=self._minio_manager_settings.region,
                    http_client=None
                )

                if hasattr(self._client._http, 'connection_pool_kw'):
                    self._client._http.connection_pool_kw['timeout'] = timeout

                await self._verify_connection()

                self._is_started = True
                logger.info("MinioClient started successfully")

            except S3Error as e:
                logger.error(
                    "S3Error during MinioClient startup",
                    extra={
                        "error_code": e.code,
                        "error_message": str(e)
                    },
                    exc_info=True
                )
                self._client = None
                raise MinioConnectionException(f"Failed to connect to MinIO: {e.code}") from e

            except Exception as e:
                logger.exception("Failed to start MinioClient")
                self._client = None
                raise MinioConnectionException("Failed to start MinIO client") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=10
        ),
        retry=retry_if_exception_type((S3Error, InvalidResponseError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _verify_connection(
            self
    ) -> None:
        if not self._client:
            raise RuntimeError("Client not initialized")

        logger.info("Verifying MinIO connection...")

        try:
            buckets = await asyncio.to_thread(self._client.list_buckets)
            logger.info(f"MinIO connection verified successfully. Found {len(buckets)} buckets")

        except Exception as e:
            logger.error(f"MinIO connection verification failed: {str(e)}")
            raise

    async def stop(
            self
    ) -> None:
        async with self._lock:
            if not self._is_started:
                logger.debug("MinioClient already stopped")
                return

            logger.info("Stopping MinioClient")

            try:
                metrics = self.get_metrics()
                logger.info(
                    "Final MinIO metrics",
                    extra=metrics
                )

                self._client = None
                self._is_started = False

                logger.info("MinioClient stopped successfully")

            except Exception as e:
                logger.error(
                    "Error stopping MinioClient",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    },
                    exc_info=True
                )
                self._client = None
                self._is_started = False

    @property
    def is_started(
            self
    ) -> bool:
        return self._is_started

    @property
    def client(
            self
    ) -> Minio:
        if not self._is_started or not self._client:
            logger.error("Attempted to access uninitialized MinioClient")
            raise MinioManagerNotInitializedException("MinioClient not started. Call start() first.")
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=10
        ),
        retry=retry_if_exception_type(S3Error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def ensure_bucket(
            self,
            bucket_name: str
    ) -> None:
        client = self.client

        try:
            exists = await asyncio.to_thread(
                client.bucket_exists,
                bucket_name
            )

            if not exists:
                logger.info(f"Creating bucket: {bucket_name}")
                await asyncio.to_thread(
                    client.make_bucket,
                    bucket_name,
                    location=self._minio_manager_settings.region
                )
                logger.info(f"Bucket created successfully: {bucket_name}")
            else:
                logger.debug(f"Bucket already exists: {bucket_name}")

            self._operation_count += 1

        except S3Error as e:
            self._error_count += 1
            logger.error(
                "S3Error ensuring bucket",
                extra={
                    "bucket": bucket_name,
                    "error_code": e.code,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise MinioBucketException(f"Failed to ensure bucket {bucket_name}: {e.code}") from e

        except Exception as e:
            self._error_count += 1
            logger.exception("Unexpected error ensuring bucket")
            raise MinioBucketException(f"Failed to ensure bucket {bucket_name}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=10
        ),
        retry=retry_if_exception_type(S3Error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def upload_file(
            self,
            bucket_name: str,
            object_name: str,
            file_path: str,
            content_type: Optional[str] = None,
            metadata: Optional[Dict[str, str]] = None
    ) -> None:
        client = self.client

        try:
            logger.debug(
                f"Uploading file to MinIO",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "file_path": file_path
                }
            )

            if self._minio_manager_settings.auto_create_bucket:
                await self.ensure_bucket(bucket_name)

            result = await asyncio.to_thread(
                client.fput_object,
                bucket_name,
                object_name,
                file_path,
                content_type=content_type,
                metadata=metadata
            )

            self._operation_count += 1
            self._upload_count += 1

            logger.info(
                f"File uploaded successfully",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "etag": result.etag
                }
            )

        except S3Error as e:
            self._error_count += 1
            logger.error(
                "S3Error uploading file",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "error_code": e.code
                },
                exc_info=True
            )
            raise MinioOperationException(f"Failed to upload file {object_name}: {e.code}") from e

        except Exception as e:
            self._error_count += 1
            logger.exception("Unexpected error uploading file")
            raise MinioOperationException(f"Failed to upload file {object_name}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=10
        ),
        retry=retry_if_exception_type(S3Error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def upload_data(
            self,
            bucket_name: str,
            object_name: str,
            data: bytes,
            content_type: Optional[str] = None,
            metadata: Optional[Dict[str, str]] = None
    ) -> None:
        client = self.client

        try:
            logger.debug(
                f"Uploading data to MinIO",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "size_bytes": len(data)
                }
            )

            if self._minio_manager_settings.auto_create_bucket:
                await self.ensure_bucket(bucket_name)

            data_stream = BytesIO(data)
            data_length = len(data)

            result = await asyncio.to_thread(
                client.put_object,
                bucket_name,
                object_name,
                data_stream,
                data_length,
                content_type=content_type,
                metadata=metadata
            )

            self._operation_count += 1
            self._upload_count += 1
            self._bytes_uploaded += data_length

            logger.info(
                f"Data uploaded successfully",
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
                "S3Error uploading data",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "error_code": e.code
                },
                exc_info=True
            )
            raise MinioOperationException(f"Failed to upload data {object_name}: {e.code}") from e

        except Exception as e:
            self._error_count += 1
            logger.exception("Unexpected error uploading data")
            raise MinioOperationException(f"Failed to upload data {object_name}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=10
        ),
        retry=retry_if_exception_type(S3Error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def download_file(
            self,
            bucket_name: str,
            object_name: str,
            file_path: str
    ) -> None:
        client = self.client

        try:
            logger.debug(
                f"Downloading file from MinIO",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "file_path": file_path
                }
            )

            await asyncio.to_thread(
                client.fget_object,
                bucket_name,
                object_name,
                file_path
            )

            self._operation_count += 1
            self._download_count += 1

            logger.info(
                f"File downloaded successfully",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "file_path": file_path
                }
            )

        except S3Error as e:
            self._error_count += 1
            logger.error(
                "S3Error downloading file",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "error_code": e.code
                },
                exc_info=True
            )
            raise MinioOperationException(f"Failed to download file {object_name}: {e.code}") from e

        except Exception as e:
            self._error_count += 1
            logger.exception("Unexpected error downloading file")
            raise MinioOperationException(f"Failed to download file {object_name}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=10
        ),
        retry=retry_if_exception_type(S3Error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def download_data(
            self,
            bucket_name: str,
            object_name: str
    ) -> bytes:
        client = self.client

        try:
            logger.debug(
                f"Downloading data from MinIO",
                extra={
                    "bucket": bucket_name,
                    "object": object_name
                }
            )

            response = await asyncio.to_thread(
                client.get_object,
                bucket_name,
                object_name
            )

            data = await asyncio.to_thread(response.read)
            await asyncio.to_thread(response.close)
            await asyncio.to_thread(response.release_conn)

            self._operation_count += 1
            self._download_count += 1
            self._bytes_downloaded += len(data)

            logger.info(
                f"Data downloaded successfully",
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
                "S3Error downloading data",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "error_code": e.code
                },
                exc_info=True
            )
            raise MinioOperationException(f"Failed to download data {object_name}: {e.code}") from e

        except Exception as e:
            self._error_count += 1
            logger.exception("Unexpected error downloading data")
            raise MinioOperationException(f"Failed to download data {object_name}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=10
        ),
        retry=retry_if_exception_type(S3Error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def delete_object(
            self,
            bucket_name: str,
            object_name: str
    ) -> None:
        client = self.client

        try:
            logger.debug(
                f"Deleting object from MinIO",
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
                f"Object deleted successfully",
                extra={
                    "bucket": bucket_name,
                    "object": object_name
                }
            )

        except S3Error as e:
            self._error_count += 1
            logger.error(
                "S3Error deleting object",
                extra={
                    "bucket": bucket_name,
                    "object": object_name,
                    "error_code": e.code
                },
                exc_info=True
            )
            raise MinioOperationException(f"Failed to delete object {object_name}: {e.code}") from e

        except Exception as e:
            self._error_count += 1
            logger.exception("Unexpected error deleting object")
            raise MinioOperationException(f"Failed to delete object {object_name}") from e

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=10
        ),
        retry=retry_if_exception_type(S3Error),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
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

        except Exception as e:
            self._error_count += 1
            logger.exception("Error checking object existence")
            raise

    async def get_presigned_url(
            self,
            bucket_name: str,
            object_name: str,
            expires: Optional[int] = None,
            method: str = "GET"
    ) -> str:
        client = self.client

        if expires is None:
            expires = self._minio_manager_settings.presigned_url_expiry

        try:
            url = await asyncio.to_thread(
                client.presigned_url,
                method,
                bucket_name,
                object_name,
                expires=timedelta(
                    seconds=expires
                )
            )

            self._operation_count += 1
            return url

        except Exception as e:
            self._error_count += 1
            logger.exception("Error generating presigned URL")
            raise MinioOperationException(f"Failed to generate presigned URL for {object_name}") from e

    async def list_objects(
            self,
            bucket_name: str,
            prefix: Optional[str] = None,
            recursive: bool = False
    ) -> List[Dict[str, Any]]:
        client = self.client

        try:
            objects = await asyncio.to_thread(
                client.list_objects,
                bucket_name,
                prefix=prefix,
                recursive=recursive
            )

            objects_list = []
            for obj in objects:
                objects_list.append({
                    "name": obj.object_name,
                    "size": obj.size,
                    "etag": obj.etag,
                    "last_modified": obj.last_modified,
                    "content_type": obj.content_type,
                })

            self._operation_count += 1
            return objects_list

        except Exception as e:
            self._error_count += 1
            logger.exception("Error listing objects")
            raise MinioOperationException(f"Failed to list objects in {bucket_name}") from e

    async def health_check(
            self
    ) -> Dict[str, Any]:
        if not self._is_started or not self._client:
            health_data = {
                "status": "unhealthy",
                "started": False,
                "error": "MinIO client not started",
                "timestamp": time.time(),
            }
            self._last_health_check = health_data
            return health_data

        try:
            start_time = time.time()

            await asyncio.to_thread(self._client.list_buckets)

            latency_ms = (time.time() - start_time) * 1000

            health_data = {
                "status": "healthy",
                "started": True,
                "latency_ms": round(latency_ms, 2),
                "timestamp": time.time(),
                "endpoint": self._minio_manager_settings.endpoint_safe,
                "metrics": self.get_metrics(),
            }

            self._last_health_check = health_data
            return health_data

        except S3Error as e:
            logger.warning(
                "MinIO health check failed (S3Error)",
                extra={
                    "error_code": e.code,
                    "error_message": str(e)
                }
            )
            health_data = {
                "status": "unhealthy",
                "started": True,
                "error": f"S3Error: {e.code}",
                "timestamp": time.time(),
            }
            self._last_health_check = health_data
            return health_data

        except Exception as e:
            logger.warning(
                "MinIO health check failed",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                }
            )
            health_data = {
                "status": "unhealthy",
                "started": True,
                "error": str(e),
                "timestamp": time.time(),
            }
            self._last_health_check = health_data
            return health_data

    def get_metrics(
            self
    ) -> Dict[str, int]:
        return {
            "operation_count": self._operation_count,
            "error_count": self._error_count,
            "upload_count": self._upload_count,
            "download_count": self._download_count,
            "bytes_uploaded": self._bytes_uploaded,
            "bytes_downloaded": self._bytes_downloaded,
        }

    async def __aenter__(
            self
    ):
        await self.start()
        return self

    async def __aexit__(
            self,
            exc_type,
            exc_val,
            exc_tb
    ):
        await self.stop()
