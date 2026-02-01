import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(
    frozen=True,
    kw_only=True
)
class DocumentStorageConfiguration:
    DEFAULT_BUCKET_NAME: str = "documents"

    bucket_name: str = DEFAULT_BUCKET_NAME

    def __post_init__(
            self
    ) -> None:
        try:
            self._validate_all()
            logger.info("DocumentStorageConfiguration initialized successfully")
        except ValueError as e:
            logger.error(
                "DocumentStorageConfiguration validation failed",
                extra={
                    "error": str(e)
                },
                exc_info=True
            )
            raise

    def _validate_all(
            self
    ) -> None:
        self._validate_bucket_name()

    def _validate_bucket_name(
            self
    ) -> None:
        if (not self.bucket_name
                or not self.bucket_name.strip()):
            raise ValueError("bucket_name no puede estar vacío")

        if (len(self.bucket_name) < 3
                or len(self.bucket_name) > 63):
            raise ValueError(
                f"bucket_name debe tener entre 3 y 63 caracteres, se recibió: {len(self.bucket_name)}"
            )

        if not self.bucket_name.islower():
            raise ValueError("bucket_name debe estar en minúsculas")

        if not all(c.isalnum() or c in ['-', '.'] for c in self.bucket_name):
            raise ValueError("bucket_name solo puede contener letras minúsculas, números, guiones y puntos")
