import logging
from typing import Optional
from asyncio import Lock
from minio import Minio
from minio.error import S3Error

from app.infrastructure.persistence.storages.minio_client.exceptions.minio_client_exception import (
    MinioConnectionError,
    MinioClientNotInitializedError,
    MinioBucketError
)
from app.infrastructure.persistence.storages.minio_client.interfaces.minio_client_interface import MinioClientInterface
from app.infrastructure.persistence.storages.minio_client.minio_client_configuration import MinioClientConfiguration

logger = logging.getLogger(__name__)


class MinioClient(MinioClientInterface):
    def __init__(
            self,
            minio_client_configuration: MinioClientConfiguration
    ) -> None:
        self._minio_client_configuration = minio_client_configuration

        self._client: Optional[Minio] = None
        self._lock = Lock()

        logger.info("MinioClient initialized successfully")

    @classmethod
    def create(
            cls,
            minio_endpoint: str,
            minio_access_key: str,
            minio_secret_key: str,
            minio_secure: Optional[bool] = None,
            minio_region: Optional[str] = None
    ) -> "MinioClient":
        config_kwargs = {}

        if minio_endpoint is not None:
            config_kwargs['minio_endpoint'] = minio_endpoint
        if minio_access_key is not None:
            config_kwargs['minio_access_key'] = minio_access_key
        if minio_secret_key is not None:
            config_kwargs['minio_secret_key'] = minio_secret_key
        if minio_secure is not None:
            config_kwargs['minio_secure'] = minio_secure
        if minio_region is not None:
            config_kwargs['minio_region'] = minio_region

        minio_client_configuration = MinioClientConfiguration(**config_kwargs)

        return cls(
            minio_client_configuration=minio_client_configuration
        )

    async def start(
            self
    ) -> None:
        async with self._lock:
            if self._client is not None:
                logger.debug("MinioClient already started")
                return

            logger.info("Starting MinioClient connection")

            try:
                self._client = Minio(
                    endpoint=self._minio_client_configuration.minio_endpoint,
                    access_key=self._minio_client_configuration.minio_access_key,
                    secret_key=self._minio_client_configuration.minio_secret_key,
                    secure=self._minio_client_configuration.minio_secure,
                    region=self._minio_client_configuration.minio_region
                )

                buckets = self._client.list_buckets()
                logger.debug(f"Connected to Minio, found {len(buckets)} buckets")

                logger.info("MinioClient started successfully")

            except S3Error as e:
                logger.error(
                    "S3Error during MinioClient initialization",
                    extra={
                        "error_code": e.code,
                        "error_message": str(e)
                    },
                    exc_info=True
                )
                self._client = None
                raise MinioConnectionError(f"Failed to connect to Minio: {e.code}") from e
            except Exception as e:
                logger.exception("Failed to initialize MinioClient")
                self._client = None
                raise MinioConnectionError("Failed to start Minio client") from e

    async def stop(
            self
    ) -> None:
        async with self._lock:
            if self._client is None:
                logger.debug("MinioClient already stopped")
                return

            logger.info("Stopping MinioClient connection")

            try:
                self._client = None
                logger.info("MinioClient stopped successfully")

            except Exception as e:
                logger.error(
                    "Error closing MinioClient",
                    extra={
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    },
                    exc_info=True
                )
                self._client = None

    @property
    def is_started(
            self
    ) -> bool:
        return self._client is not None

    @property
    def client(
            self
    ) -> Minio:
        if self._client is None:
            logger.error("Attempted to access uninitialized MinioClient")
            raise MinioClientNotInitializedError("MinioClient not started. Call start() first.")
        return self._client

    def ensure_bucket(
            self,
            bucket_name: str
    ) -> None:
        client = self.client

        try:
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name, location=self._minio_client_configuration.minio_region)
                logger.info("Bucket created successfully")
            else:
                logger.debug("Bucket already exists")

        except S3Error as e:
            logger.error(
                "S3Error ensuring bucket",
                extra={
                    "error_code": e.code,
                    "error_message": str(e)
                },
                exc_info=True
            )
            raise MinioBucketError(f"Failed to ensure bucket {bucket_name}: {e.code}") from e
        except Exception as e:
            logger.exception("Unexpected error ensuring bucket")
            raise MinioBucketError(f"Failed to ensure bucket {bucket_name}") from e

    async def health_check(
            self
    ) -> bool:
        if self._client is None:
            logger.warning("Health check failed: MinioClient not started")
            return False

        try:
            self._client.list_buckets()
            logger.debug("Minio health check passed")
            return True
        except S3Error as e:
            logger.warning(
                "Minio health check failed (S3Error)",
                extra={
                    "error_code": e.code,
                    "error_message": str(e)
                },
                exc_info=True
            )
            return False
        except Exception as e:
            logger.warning(
                "Minio health check failed",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e)
                },
                exc_info=True
            )
            return False
