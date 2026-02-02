import logging
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MinioClientConfiguration:
    DEFAULT_SECURE: Final[bool] = True
    DEFAULT_REGION: Final[str] = "us-east-1"

    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool = DEFAULT_SECURE
    minio_region: str = DEFAULT_REGION

    def __post_init__(
            self
    ) -> None:
        try:
            self._validate_all()
            logger.info("MinioClientConfiguration initialized successfully")
        except ValueError as e:
            logger.error(
                "MinioClientConfiguration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(self) -> None:
        self._validate_minio_endpoint()
        self._validate_minio_access_key()
        self._validate_minio_secret_key()
        self._validate_minio_region()

    def _validate_minio_endpoint(
            self
    ) -> None:
        if (not self.minio_endpoint
                or not self.minio_endpoint.strip()):
            raise ValueError("minio_endpoint no puede estar vacío")

        try:
            parsed = urlparse(f"http://{self.minio_endpoint}")
            if not parsed.netloc:
                raise ValueError("minio_endpoint debe ser un endpoint válido")
        except Exception as e:
            raise ValueError(f"minio_endpoint no es válido: {self.minio_endpoint}") from e

    def _validate_minio_access_key(
            self
    ) -> None:
        if (not self.minio_access_key
                or not self.minio_access_key.strip()):
            raise ValueError("minio_access_key no puede estar vacío")

    def _validate_minio_secret_key(
            self
    ) -> None:
        if (not self.minio_secret_key
                or not self.minio_secret_key.strip()):
            raise ValueError("minio_secret_key no puede estar vacío")

    def _validate_minio_region(
            self
    ) -> None:
        if (not self.minio_region
                or not self.minio_region.strip()):
            raise ValueError("minio_region no puede estar vacío")
