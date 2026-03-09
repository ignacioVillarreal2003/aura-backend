import logging
import time
from typing import Any, Dict, List, Optional
from fastapi import UploadFile

from app.infrastructure.persistence.storages.document_storage.exceptions.document_storage_exception import (
    DocumentDeleteException,
    DocumentDownloadException,
    DocumentStorageException,
    DocumentUploadException,
    DocumentValidationException,
    DocumentExtensionException,
    DocumentSizeLimitException,
    DocumentNotFoundException
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)
from app.infrastructure.persistence.storages.document_storage.document_storage_settings import DocumentStorageSettings
from app.infrastructure.persistence.storages.minio_manager.exceptions.minio_manager_exception import (
    MinioDownloadException,
    MinioDeleteException
)
from app.infrastructure.persistence.storages.minio_manager.interfaces.minio_manager_interface import (
    MinioManagerInterface
)

logger = logging.getLogger(__name__)


class DocumentStorage(DocumentStorageInterface):
    def __init__(
            self,
            minio_manager: MinioManagerInterface,
            document_storage_settings: Optional[DocumentStorageSettings] = None
    ) -> None:
        self._minio_manager = minio_manager
        self._document_storage_settings = document_storage_settings or DocumentStorageSettings()
        self._bucket_name = self._document_storage_settings.bucket_name

        self._upload_count: int = 0
        self._download_count: int = 0
        self._delete_count: int = 0
        self._error_count: int = 0
        self._bytes_uploaded: int = 0
        self._bytes_downloaded: int = 0

    async def start(self) -> None:
        try:
            if self._document_storage_settings.auto_create_bucket_if_missing:
                logger.info(
                    "Ensuring bucket exists",
                    extra={
                        "bucket": self._bucket_name
                    }
                )
                await self._minio_manager.ensure_bucket(self._bucket_name)

            logger.info(
                "DocumentStorage started successfully",
                extra={
                    "bucket": self._bucket_name
                }
            )

        except Exception as e:
            raise DocumentStorageException(f"Failed to start DocumentStorage: {e}") from e

    async def upload_document(
            self,
            file: UploadFile,
            document_id: Optional[str] = None,
            additional_metadata: Optional[Dict[str, str]] = None
    ) -> str:
        start_time = time.monotonic()

        try:
            if not file.filename:
                raise DocumentValidationException("Filename cannot be empty")

            if not self._document_storage_settings.is_extension_allowed(file.filename):
                allowed = (
                    ", ".join(self._document_storage_settings.allowed_file_extensions)
                    if self._document_storage_settings.allowed_file_extensions
                    else "all"
                )
                raise DocumentExtensionException(f"File extension not allowed. Permitted: {allowed}")

            content = await file.read()
            file_size = len(content)

            self._validate_file_size(file_size)

            object_name = self._document_storage_settings.generate_object_name(
                original_filename=file.filename,
                document_id=document_id
            )

            metadata: Dict[str, str] = {}
            if self._document_storage_settings.attach_metadata_to_objects:
                metadata["original_filename"] = self._document_storage_settings.sanitize_metadata_value(
                    file.filename
                )
                metadata["document_id"] = document_id or "none"
                metadata["upload_timestamp"] = str(int(time.time()))

                if additional_metadata:
                    metadata.update(additional_metadata)

            await self._minio_manager.upload_data(
                bucket_name=self._bucket_name,
                object_name=object_name,
                data=content,
                content_type=(
                    file.content_type if self._document_storage_settings.send_content_type_header else None
                ),
                metadata=metadata or None
            )

            self._upload_count += 1
            self._bytes_uploaded += file_size

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "Document uploaded successfully",
                extra={
                    "object_name": object_name,
                    "original_filename": file.filename,
                    "size_bytes": file_size,
                    "elapsed_ms": elapsed_ms
                }
            )

            return object_name

        except DocumentValidationException:
            self._error_count += 1
            raise

        except Exception as e:
            self._error_count += 1
            raise DocumentUploadException(f"Failed to upload document: {e}") from e

    async def download_document(
            self,
            object_name: str
    ) -> bytes:
        start_time = time.monotonic()

        try:
            content = await self._minio_manager.download_data(
                bucket_name=self._bucket_name,
                object_name=object_name,
            )

            self._download_count += 1
            self._bytes_downloaded += len(content)

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "Document downloaded successfully",
                extra={
                    "object_name": object_name,
                    "size_bytes": len(content),
                    "elapsed_ms": elapsed_ms
                }
            )

            return content

        except MinioDownloadException as e:
            self._error_count += 1
            if e.__cause__ and hasattr(e.__cause__, "code") and e.__cause__.code == "NoSuchKey":
                raise DocumentNotFoundException(f"Document '{object_name}' not found") from e
            raise DocumentDownloadException(f"Failed to download document '{object_name}': {e}") from e

        except Exception as e:
            self._error_count += 1
            raise DocumentDownloadException(f"Failed to download document '{object_name}': {e}") from e

    async def download_document_to_file(
            self,
            object_name: str,
            file_path: str
    ) -> None:
        start_time = time.monotonic()

        try:
            await self._minio_manager.download_file(
                bucket_name=self._bucket_name,
                object_name=object_name,
                file_path=file_path
            )

            from pathlib import Path
            file_size = Path(file_path).stat().st_size
            self._download_count += 1
            self._bytes_downloaded += file_size

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "Document downloaded to file",
                extra={
                    "object_name": object_name,
                    "file_path": file_path,
                    "size_bytes": file_size,
                    "elapsed_ms": elapsed_ms
                }
            )

        except Exception as e:
            self._error_count += 1
            raise DocumentDownloadException(f"Failed to download document '{object_name}' to file: {e}") from e

    async def delete_document(
            self,
            object_name: str
    ) -> None:
        try:
            await self._minio_manager.delete_object(
                bucket_name=self._bucket_name,
                object_name=object_name
            )

            self._delete_count += 1

            logger.info(
                "Document deleted successfully",
                extra={
                    "object_name": object_name
                }
            )

        except MinioDeleteException as e:
            self._error_count += 1
            if e.__cause__ and hasattr(e.__cause__, "code") and e.__cause__.code == "NoSuchKey":
                raise DocumentNotFoundException(f"Document '{object_name}' not found") from e
            raise DocumentDeleteException(f"Failed to delete document '{object_name}': {e}") from e

        except Exception as e:
            self._error_count += 1
            raise DocumentDeleteException(f"Failed to delete document '{object_name}': {e}") from e

    async def document_exists(
            self,
            object_name: str
    ) -> bool:
        try:
            return await self._minio_manager.object_exists(
                bucket_name=self._bucket_name,
                object_name=object_name
            )

        except Exception as e:
            self._error_count += 1
            raise DocumentStorageException(f"Failed to check existence of '{object_name}': {e}") from e

    async def get_presigned_url(
            self,
            object_name: str,
            method: str = "GET",
            expires: Optional[int] = None
    ) -> str:
        expiry = (
            expires
            if expires is not None
            else self._document_storage_settings.presigned_url_expiry_seconds
        )

        try:
            url = await self._minio_manager.get_presigned_url(
                bucket_name=self._bucket_name,
                object_name=object_name,
                expires=expiry,
                method=method
            )

            logger.debug(
                "Presigned URL generated",
                extra={
                    "object_name": object_name,
                    "expires_seconds": expiry,
                    "method": method
                }
            )

            return url

        except Exception as e:
            self._error_count += 1
            raise DocumentStorageException(f"Failed to generate presigned URL for '{object_name}': {e}") from e

    async def list_documents(
            self,
            recursive: bool = True,
            prefix: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        try:
            full_prefix = self._build_prefix(prefix)

            objects = await self._minio_manager.list_objects(
                bucket_name=self._bucket_name,
                prefix=full_prefix,
                recursive=recursive
            )

            logger.debug(
                "Documents listed successfully",
                extra={
                    "prefix": full_prefix,
                    "count": len(objects)
                }
            )

            return objects

        except Exception as e:
            self._error_count += 1
            raise DocumentStorageException(f"Failed to list documents: {e}") from e

    async def health_check(self) -> Dict[str, Any]:
        try:
            minio_health = await self._minio_manager.health_check()
            minio_healthy = minio_health.get("status") == "healthy"

            bucket_accessible = False
            if minio_healthy:
                bucket_accessible = await self._probe_bucket_accessible()

            status = "healthy" if (minio_healthy and bucket_accessible) else "unhealthy"

            return {
                "status": status,
                "bucket": self._bucket_name,
                "bucket_accessible": bucket_accessible,
                "minio": minio_health,
                "metrics": self.get_metrics()
            }

        except Exception:
            logger.exception("DocumentStorage health check failed")
            return {
                "status": "unhealthy",
                "bucket": self._bucket_name,
                "error": "Health check failed — see logs for details",
            }

    def get_metrics(self) -> Dict[str, int]:
        return {
            "upload_count": self._upload_count,
            "download_count": self._download_count,
            "delete_count": self._delete_count,
            "error_count": self._error_count,
            "bytes_uploaded": self._bytes_uploaded,
            "bytes_downloaded": self._bytes_downloaded,
        }

    def _validate_file_size(
            self,
            file_size: int
    ) -> None:
        if (
                self._document_storage_settings.max_file_size_bytes is not None
                and file_size > self._document_storage_settings.max_file_size_bytes
        ):
            max_mb = self._document_storage_settings.max_file_size_bytes / (1024 * 1024)
            raise DocumentSizeLimitException(f"File too large. Maximum allowed size: {max_mb:.1f} MB")

        if file_size < self._document_storage_settings.min_file_size_bytes:
            raise DocumentSizeLimitException(
                f"File too small. Minimum size: {self._document_storage_settings.min_file_size_bytes} bytes")

    def _build_prefix(
            self,
            extra_prefix: Optional[str]
    ) -> Optional[str]:
        parts = []

        if self._document_storage_settings.object_key_prefix:
            parts.append(self._document_storage_settings.object_key_prefix)

        if extra_prefix:
            parts.append(extra_prefix.lstrip("/"))

        return "/".join(parts) if parts else None

    async def _probe_bucket_accessible(self) -> bool:
        try:
            await self._minio_manager.object_exists(
                bucket_name=self._bucket_name,
                object_name=".health_probe"
            )
            return True

        except Exception as e:
            logger.warning(
                "Bucket accessibility probe failed",
                extra={
                    "bucket": self._bucket_name,
                    "error": str(e)
                }
            )
            return False
