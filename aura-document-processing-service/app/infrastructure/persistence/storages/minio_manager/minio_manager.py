import asyncio
import logging
import time
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Optional
import urllib3
from fastapi import HTTPException, Request, status
from minio import Minio
from minio.error import InvalidResponseError, S3Error
from tenacity import before_sleep_log, retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from urllib3.exceptions import HTTPError as Urllib3HTTPError

from app.application.exceptions.app_exception import AppException
from app.infrastructure.persistence.storages.minio_manager.exceptions.minio_manager_exception import (
    MinioBucketException,
    MinioConnectionException,
    MinioDeleteException,
    MinioDownloadException,
    MinioManagerNotInitializedException,
    MinioOperationException,
    MinioUploadException
)
from app.infrastructure.persistence.storages.minio_manager.interfaces.minio_manager_interface import (
    MinioManagerInterface
)
from app.infrastructure.persistence.storages.minio_manager.minio_manager_settings import (
    MinioManagerSettings
)

logger = logging.getLogger(__name__)

_PRESIGNED_HTTP_METHODS = frozenset({"GET", "PUT", "HEAD", "DELETE"})


def _pool_http_timeout(settings: MinioManagerSettings) -> urllib3.Timeout:
    connect = float(settings.tcp_connect_timeout_seconds)
    read_t = float(settings.socket_read_timeout_seconds)
    write_t = float(settings.socket_write_timeout_seconds)
    return urllib3.Timeout(connect=connect, read=read_t, total=connect + write_t + read_t)


class MinioManager(MinioManagerInterface):
    def __init__(self, minio_manager_settings: Optional[MinioManagerSettings] = None) -> None:
        self._settings = minio_manager_settings or MinioManagerSettings()
        self._client: Optional[Minio] = None

        self._lifecycle_lock = asyncio.Lock()
        self._is_started: bool = False

        self._ensure_bucket_retried: Optional[Callable[..., Awaitable[Any]]] = None
        self._upload_file_retried: Optional[Callable[..., Awaitable[Any]]] = None
        self._upload_data_retried: Optional[Callable[..., Awaitable[Any]]] = None
        self._download_file_retried: Optional[Callable[..., Awaitable[Any]]] = None
        self._download_data_retried: Optional[Callable[..., Awaitable[Any]]] = None
        self._delete_object_retried: Optional[Callable[..., Awaitable[Any]]] = None

    async def start(
            self
    ) -> None:
        async with self._lifecycle_lock:
            if self._is_started:
                logger.debug("MinioManager is already started; skipping start.")
                return

            logger.info(
                "Starting MinioManager.",
                extra={
                    "endpoint": self._settings.endpoint_safe
                }
            )

            try:
                http_client = urllib3.PoolManager(
                    timeout=_pool_http_timeout(self._settings),
                    maxsize=self._settings.connection_pool_size,
                    retries=False
                )

                self._client = Minio(
                    **self._settings.get_minio_config(),
                    http_client=http_client
                )

                s3_retry = retry(
                    stop=stop_after_attempt(self._settings.retry_max_attempts),
                    wait=wait_exponential(
                        multiplier=self._settings.retry_backoff_multiplier,
                        min=self._settings.retry_backoff_min_seconds,
                        max=self._settings.retry_backoff_max_seconds
                    ),
                    retry=retry_if_exception_type(
                        (S3Error, InvalidResponseError, Urllib3HTTPError, OSError)
                    ),
                    before_sleep=before_sleep_log(logger, logging.WARNING),
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
                logger.info("MinioManager started successfully.")

            except asyncio.CancelledError:
                self._cleanup_resources()
                raise
            except (S3Error, InvalidResponseError, Urllib3HTTPError, OSError) as e:
                self._cleanup_resources()
                logger.exception("Failed to start MinioManager.")
                raise MinioConnectionException("Could not start the object storage client.") from e
            except Exception:
                self._cleanup_resources()
                logger.exception("Failed to start MinioManager.")
                raise

    async def stop(
            self
    ) -> None:
        async with self._lifecycle_lock:
            if not self._is_started:
                logger.debug("MinioManager is already stopped; skipping stop.")
                return

            logger.info("Stopping MinioManager.")
            self._cleanup_resources()
            logger.info("MinioManager stopped successfully.")

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
            raise MinioManagerNotInitializedException("The MinIO manager is not started; call start() first.")
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
            metadata: Optional[dict[str, str]] = None
    ) -> None:
        await self._upload_file_retried(bucket_name, object_name, file_path, content_type, metadata)

    async def upload_data(
            self,
            bucket_name: str,
            object_name: str,
            data: bytes,
            content_type: Optional[str] = None,
            metadata: Optional[dict[str, str]] = None
    ) -> None:
        await self._upload_data_retried(bucket_name, object_name, data, content_type, metadata)

    async def download_file(
            self,
            bucket_name: str,
            object_name: str,
            file_path: str
    ) -> None:
        await self._download_file_retried(bucket_name, object_name, file_path)

    async def download_data(
            self,
            bucket_name: str,
            object_name: str
    ) -> bytes:
        return await self._download_data_retried(bucket_name, object_name)

    async def download_data_stream(
            self,
            bucket_name: str,
            object_name: str,
            chunk_size: int,
    ) -> AsyncIterator[bytes]:
        client = self.client
        response = None
        try:
            response = await asyncio.to_thread(client.get_object, bucket_name, object_name)
            while True:
                chunk = await asyncio.to_thread(response.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        except S3Error as e:
            logger.error(
                "S3 error while streaming object data.",
                extra={
                    "bucket": bucket_name,
                    "s3_error_code": e.code,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )
            raise MinioDownloadException("Failed to stream the object.") from e
        except (InvalidResponseError, Urllib3HTTPError, OSError) as e:
            logger.exception(
                "Transport error while streaming object data.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                },
            )
            raise MinioDownloadException("Failed to stream the object.") from e
        finally:
            if response is not None:
                await asyncio.to_thread(response.close)
                await asyncio.to_thread(response.release_conn)

    async def delete_object(
            self,
            bucket_name: str,
            object_name: str
    ) -> None:
        await self._delete_object_retried(bucket_name, object_name)

    async def object_exists(
            self,
            bucket_name: str,
            object_name: str
    ) -> bool:
        client = self.client
        try:
            await asyncio.to_thread(client.stat_object, bucket_name, object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise

    async def get_presigned_url(
            self,
            bucket_name: str,
            object_name: str,
            expires: Optional[int] = None,
            method: str = "GET"
    ) -> str:
        method_norm = method.strip().upper()
        if method_norm not in _PRESIGNED_HTTP_METHODS:
            raise AppException(
                f"Unsupported presigned HTTP method: {method!r}.",
                status_code=400,
            )

        client = self.client
        expiry_seconds = expires if expires is not None else self._settings.presigned_url_expiry_seconds

        try:
            url: str = await asyncio.to_thread(
                client.presigned_url,
                method_norm,
                bucket_name,
                object_name,
                expires=timedelta(seconds=expiry_seconds)
            )
            return url
        except asyncio.CancelledError:
            raise
        except (S3Error, InvalidResponseError, Urllib3HTTPError, OSError) as e:
            logger.exception(
                "Failed to generate a presigned URL.",
                extra={
                    "bucket": bucket_name,
                    "method": method_norm,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )
            raise MinioOperationException("Failed to generate a presigned URL.") from e
        except Exception:
            logger.exception(
                "Failed to generate a presigned URL (unexpected error).",
                extra={
                    "bucket": bucket_name,
                    "method": method_norm,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )
            raise

    async def list_objects(
            self,
            bucket_name: str,
            prefix: Optional[str] = None,
            recursive: bool = False
    ) -> list[dict[str, Any]]:
        client = self.client

        try:
            def _collect() -> list[dict[str, Any]]:
                return [
                    {
                        "name": obj.object_name,
                        "size": obj.size,
                        "etag": obj.etag,
                        "last_modified": obj.last_modified,
                        "content_type": obj.content_type
                    }
                    for obj in client.list_objects(bucket_name, prefix=prefix, recursive=recursive)
                ]

            result = await asyncio.to_thread(_collect)

            list_ok_extra: dict[str, Any] = {
                "bucket": bucket_name,
                "count": len(result)
            }
            if prefix:
                list_ok_extra["prefix_suffix"] = prefix[-self._settings.list_prefix_log_suffix_chars:]
            logger.debug(
                "Listed objects successfully.",
                extra=list_ok_extra,
            )
            return result

        except asyncio.CancelledError:
            raise
        except (S3Error, InvalidResponseError, Urllib3HTTPError, OSError) as e:
            list_err_extra: dict[str, Any] = {
                "bucket": bucket_name
            }
            if prefix:
                list_err_extra["prefix_suffix"] = prefix[-self._settings.list_prefix_log_suffix_chars:]
            logger.exception(
                "Failed to list objects.",
                extra=list_err_extra
            )
            raise MinioOperationException("Failed to list objects.") from e
        except Exception:
            list_err_extra = {"bucket": bucket_name}
            if prefix:
                list_err_extra["prefix_suffix"] = prefix[-self._settings.list_prefix_log_suffix_chars:]
            logger.exception("Failed to list objects (unexpected error).", extra=list_err_extra)
            raise

    async def health_check(
            self,
            detailed: bool = False,
    ) -> dict[str, Any]:
        if not self._is_started or not self._client:
            return {
                "status": "unhealthy",
                "started": False,
                "error": "The object storage client is not started."
            }

        try:
            start_time = time.monotonic()
            await asyncio.to_thread(self._client.list_buckets)
            latency_ms = round((time.monotonic() - start_time) * 1000, 2)

            base: dict[str, Any] = {
                "status": "healthy",
                "started": True,
                "latency_ms": latency_ms,
            }
            if detailed:
                base["endpoint"] = self._settings.endpoint_safe
            return base

        except asyncio.CancelledError:
            raise
        except S3Error as e:
            logger.warning(
                "Object storage health check failed.",
                extra={
                    "s3_error_code": e.code
                }
            )
            err: dict[str, Any] = {
                "status": "unhealthy",
                "started": True,
                "error": "S3 service error",
            }
            if detailed:
                err["s3_error_code"] = e.code
            return err

        except (InvalidResponseError, Urllib3HTTPError, OSError):
            logger.warning("Object storage health check failed (transport error).")
            return {
                "status": "unhealthy",
                "started": True,
                "error": "Health check failed; see application logs for details."
            }

        except Exception:
            logger.warning("Object storage health check failed; see application logs for details.")
            return {
                "status": "unhealthy",
                "started": True,
                "error": "Health check failed; see application logs for details."
            }

    async def __aenter__(
            self
    ) -> "MinioManager":
        await self.start()
        return self

    async def __aexit__(
            self,
            exc_type,
            exc_val,
            exc_tb
    ) -> None:
        await self.stop()

    def _cleanup_resources(
            self
    ) -> None:
        self._client = None
        self._ensure_bucket_retried = None
        self._upload_file_retried = None
        self._upload_data_retried = None
        self._download_file_retried = None
        self._download_data_retried = None
        self._delete_object_retried = None
        self._is_started = False

    async def _verify_connection(
            self
    ) -> None:
        if not self._client:
            raise RuntimeError("Client not initialised before connection verification")

        @retry(
            stop=stop_after_attempt(self._settings.retry_max_attempts),
            wait=wait_exponential(
                multiplier=self._settings.retry_backoff_multiplier,
                min=self._settings.retry_backoff_min_seconds,
                max=self._settings.retry_backoff_max_seconds
            ),
            retry=retry_if_exception_type(
                (S3Error, InvalidResponseError, Urllib3HTTPError, OSError)
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True
        )
        async def _attempt() -> None:
            logger.info("Verifying MinIO connection.")
            await asyncio.to_thread(self._client.list_buckets)
            logger.info("MinIO connection verified successfully.")

        await _attempt()

    async def _ensure_bucket_core(
            self,
            bucket_name: str
    ) -> None:
        client = self.client
        try:
            exists: bool = await asyncio.to_thread(client.bucket_exists, bucket_name)
            if not exists:
                logger.info(
                    "Creating bucket.",
                    extra={
                        "bucket": bucket_name
                    }
                )
                await asyncio.to_thread(
                    client.make_bucket, bucket_name, location=self._settings.region
                )
                logger.info(
                    "Bucket created successfully.",
                    extra={
                        "bucket": bucket_name
                    }
                )
            else:
                logger.debug(
                    "Bucket already exists.",
                    extra={
                        "bucket": bucket_name
                    }
                )

        except S3Error as e:
            logger.error(
                "S3 error while ensuring bucket exists.",
                extra={
                    "bucket": bucket_name,
                    "s3_error_code": e.code
                }
            )
            raise MinioBucketException("Failed to ensure the bucket exists.") from e

        except (InvalidResponseError, Urllib3HTTPError, OSError) as e:
            logger.exception(
                "Transport error while ensuring bucket exists.",
                extra={"bucket": bucket_name},
            )
            raise MinioBucketException("Failed to ensure the bucket exists.") from e

        except Exception:
            raise

    async def _upload_file_core(
            self,
            bucket_name: str,
            object_name: str,
            file_path: str,
            content_type: Optional[str],
            metadata: Optional[dict[str, str]]
    ) -> None:
        client = self.client
        try:
            file_size = Path(file_path).stat().st_size
            logger.debug(
                "Uploading file to MinIO.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )

            if self._settings.auto_create_bucket_if_missing:
                await self._ensure_bucket_retried(bucket_name)

            result = await asyncio.to_thread(
                client.fput_object,
                bucket_name,
                object_name,
                file_path,
                content_type=content_type,
                metadata=metadata
            )

            logger.info(
                "File uploaded successfully.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else "",
                    "size_bytes": file_size,
                    "etag": result.etag
                }
            )

        except S3Error as e:
            logger.error(
                "S3 error while uploading file.",
                extra={
                    "bucket": bucket_name,
                    "s3_error_code": e.code,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )
            raise MinioUploadException("Failed to upload the object.") from e

        except (InvalidResponseError, Urllib3HTTPError, OSError) as e:
            logger.exception(
                "Transport error while uploading file.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                },
            )
            raise MinioUploadException("Failed to upload the object.") from e

        except Exception:
            raise

    async def _upload_data_core(
            self,
            bucket_name: str,
            object_name: str,
            data: bytes,
            content_type: Optional[str],
            metadata: Optional[dict[str, str]]
    ) -> None:
        client = self.client
        data_length = len(data)
        try:
            logger.debug(
                "Uploading data to MinIO.",
                extra={
                    "bucket": bucket_name,
                    "size_bytes": data_length,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )

            if self._settings.auto_create_bucket_if_missing:
                await self._ensure_bucket_retried(bucket_name)

            result = await asyncio.to_thread(
                client.put_object,
                bucket_name,
                object_name,
                BytesIO(data),
                data_length,
                content_type=content_type,
                metadata=metadata
            )

            logger.info(
                "Data uploaded successfully.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else "",
                    "size_bytes": data_length,
                    "etag": result.etag
                }
            )

        except S3Error as e:
            logger.error(
                "S3 error while uploading data.",
                extra={
                    "bucket": bucket_name,
                    "s3_error_code": e.code,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )
            raise MinioUploadException("Failed to upload the object.") from e

        except (InvalidResponseError, Urllib3HTTPError, OSError) as e:
            logger.exception(
                "Transport error while uploading data.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                },
            )
            raise MinioUploadException("Failed to upload the object.") from e

        except Exception:
            raise

    async def _download_file_core(
            self,
            bucket_name: str,
            object_name: str,
            file_path: str
    ) -> None:
        client = self.client
        try:
            logger.debug(
                "Downloading file from MinIO.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )

            await asyncio.to_thread(client.fget_object, bucket_name, object_name, file_path)

            file_size = Path(file_path).stat().st_size
            logger.info(
                "File downloaded successfully.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else "",
                    "size_bytes": file_size
                }
            )

        except S3Error as e:
            logger.error(
                "S3 error while downloading file.",
                extra={
                    "bucket": bucket_name,
                    "s3_error_code": e.code,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )
            raise MinioDownloadException("Failed to download the object.") from e

        except (InvalidResponseError, Urllib3HTTPError, OSError) as e:
            logger.exception(
                "Transport error while downloading file.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                },
            )
            raise MinioDownloadException("Failed to download the object.") from e

        except Exception:
            raise

    async def _download_data_core(
            self,
            bucket_name: str,
            object_name: str
    ) -> bytes:
        client = self.client
        try:
            logger.debug(
                "Downloading data from MinIO.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
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

            logger.info(
                "Data downloaded successfully.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else "",
                    "size_bytes": len(data)
                }
            )
            return data

        except S3Error as e:
            logger.error(
                "S3 error while downloading data.",
                extra={
                    "bucket": bucket_name,
                    "s3_error_code": e.code,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )
            raise MinioDownloadException("Failed to download the object.") from e

        except (InvalidResponseError, Urllib3HTTPError, OSError) as e:
            logger.exception(
                "Transport error while downloading data.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                },
            )
            raise MinioDownloadException("Failed to download the object.") from e

        except Exception:
            raise

    async def _delete_object_core(
            self,
            bucket_name: str,
            object_name: str
    ) -> None:
        client = self.client
        try:
            logger.debug(
                "Deleting object from MinIO.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )

            await asyncio.to_thread(client.remove_object, bucket_name, object_name)

            logger.info(
                "Object deleted successfully.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )

        except S3Error as e:
            logger.error(
                "S3 error while deleting object.",
                extra={
                    "bucket": bucket_name,
                    "s3_error_code": e.code,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )
            raise MinioDeleteException("Failed to delete the object.") from e

        except (InvalidResponseError, Urllib3HTTPError, OSError) as e:
            logger.exception(
                "Transport error while deleting object.",
                extra={
                    "bucket": bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                },
            )
            raise MinioDeleteException("Failed to delete the object.") from e

        except Exception:
            raise


async def get_minio_manager(
        request: Request
) -> MinioManagerInterface:
    minio_manager = getattr(request.app.state, "minio_manager", None)
    if minio_manager is None:
        logger.error("The MinIO manager was not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is not configured"
        )
    if not minio_manager.is_started:
        logger.error("The MinIO manager exists on the application but has not been started.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is not available"
        )
    return minio_manager


async def get_minio_client(
        request: Request
) -> Minio:
    try:
        minio_manager = await get_minio_manager(request)
        return minio_manager.client
    except MinioManagerNotInitializedException:
        logger.error("The MinIO client was requested but the manager is not started.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object storage is not available"
        ) from None
    except asyncio.CancelledError:
        raise
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error while retrieving the MinIO client.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A storage error occurred"
        ) from None
