import logging
import time
from pathlib import Path
from typing import Any, Optional
from fastapi import HTTPException, Request, status, UploadFile

from app.infrastructure.persistence.storages.document_storage.document_storage_settings import DocumentStorageSettings
from app.infrastructure.persistence.storages.document_storage.exceptions.document_storage_exception import (
    DocumentDeleteException,
    DocumentDownloadException,
    DocumentExtensionException,
    DocumentNotFoundException,
    DocumentSizeLimitException,
    DocumentStorageException,
    DocumentUploadException,
    DocumentValidationException
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)
from app.infrastructure.persistence.storages.minio_manager.exceptions.minio_manager_exception import (
    MinioDeleteException,
    MinioDownloadException
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
        self._settings = document_storage_settings or DocumentStorageSettings()
        self._bucket_name = self._settings.bucket_name

    async def start(
            self
    ) -> None:
        try:
            if self._settings.auto_create_bucket_if_missing:
                logger.info(
                    "Ensuring the bucket exists.",
                    extra={
                        "bucket": self._bucket_name
                    }
                )
                await self._minio_manager.ensure_bucket(self._bucket_name)

            logger.info(
                "Document storage started successfully.",
                extra={
                    "bucket": self._bucket_name
                }
            )

        except Exception as e:
            raise DocumentStorageException("Failed to start document storage.") from e

    async def upload_document(
            self,
            file: UploadFile,
            document_id: Optional[str] = None,
            additional_metadata: Optional[dict[str, str]] = None
    ) -> str:
        start_time = time.monotonic()

        try:
            if not file.filename:
                raise DocumentValidationException("Filename cannot be empty.")

            if not self._settings.is_extension_allowed(file.filename):
                allowed = (
                    ", ".join(self._settings.allowed_file_extensions)
                    if self._settings.allowed_file_extensions
                    else "all"
                )
                raise DocumentExtensionException(f"File extension not allowed. Permitted: {allowed}")

            content = await file.read()
            file_size = len(content)
            self._validate_file_size(file_size)

            object_name = self._settings.generate_object_name(
                original_filename=file.filename,
                document_id=document_id
            )

            metadata: dict[str, str] = {}
            if self._settings.attach_metadata_to_objects:
                metadata["original_filename"] = self._settings.sanitize_metadata_value(file.filename)
                metadata["document_id"] = document_id or "none"
                metadata["upload_timestamp"] = str(int(time.time()))
                if additional_metadata:
                    metadata.update(additional_metadata)

            await self._minio_manager.upload_data(
                bucket_name=self._bucket_name,
                object_name=object_name,
                data=content,
                content_type=(
                    file.content_type if self._settings.send_content_type_header else None
                ),
                metadata=metadata or None
            )

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            upload_extra: dict[str, Any] = {
                "bucket": self._bucket_name,
                "object_key_suffix": object_name[-self._settings.object_key_log_suffix_chars:] if object_name else "",
                "size_bytes": file_size,
                "elapsed_ms": elapsed_ms
            }
            if document_id:
                upload_extra["document_id"] = document_id
            logger.info(
                "The document was uploaded successfully.",
                extra=upload_extra
            )
            return object_name

        except (
                DocumentValidationException,
                DocumentExtensionException,
                DocumentSizeLimitException
        ):
            raise

        except Exception as e:
            raise DocumentUploadException("Failed to upload the document.") from e

    async def download_document(
            self,
            object_name: str
    ) -> bytes:
        start_time = time.monotonic()

        try:
            content = await self._minio_manager.download_data(
                bucket_name=self._bucket_name,
                object_name=object_name
            )

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "The document was downloaded successfully.",
                extra={
                    "bucket": self._bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else "",
                    "size_bytes": len(content),
                    "elapsed_ms": elapsed_ms
                }
            )
            return content

        except MinioDownloadException as e:
            if self._is_not_found_error(e):
                raise DocumentNotFoundException("The document was not found.") from e
            raise DocumentDownloadException("Failed to download the document.") from e

        except Exception as e:
            raise DocumentDownloadException("Failed to download the document.") from e

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

            file_size = Path(file_path).stat().st_size

            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "The document was downloaded to the target file successfully.",
                extra={
                    "bucket": self._bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else "",
                    "file_path_suffix": file_path[-self._settings.file_path_log_suffix_chars:] if file_path else "",
                    "size_bytes": file_size,
                    "elapsed_ms": elapsed_ms
                }
            )

        except MinioDownloadException as e:
            if self._is_not_found_error(e):
                raise DocumentNotFoundException("The document was not found.") from e
            raise DocumentDownloadException("Failed to download the document.") from e

        except Exception as e:
            raise DocumentDownloadException("Failed to download the document.") from e

    async def delete_document(self, object_name: str) -> None:
        try:
            await self._minio_manager.delete_object(
                bucket_name=self._bucket_name,
                object_name=object_name
            )

            logger.info(
                "The document was deleted successfully.",
                extra={
                    "bucket": self._bucket_name,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )

        except MinioDeleteException as e:
            if self._is_not_found_error(e):
                raise DocumentNotFoundException("The document was not found.") from e
            raise DocumentDeleteException("Failed to delete the document.") from e

        except Exception as e:
            raise DocumentDeleteException("Failed to delete the document.") from e

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
            raise DocumentStorageException("Failed to check whether the document exists.") from e

    async def get_presigned_url(
            self,
            object_name: str,
            method: str = "GET",
            expires: Optional[int] = None
    ) -> str:
        expiry = expires if expires is not None else self._settings.presigned_url_expiry_seconds

        try:
            url = await self._minio_manager.get_presigned_url(
                bucket_name=self._bucket_name,
                object_name=object_name,
                expires=expiry,
                method=method
            )

            logger.debug(
                "A presigned URL was generated.",
                extra={
                    "bucket": self._bucket_name,
                    "expires_seconds": expiry,
                    "method": method,
                    "object_key_suffix": object_name[
                        -self._settings.object_key_log_suffix_chars:
                    ] if object_name else ""
                }
            )
            return url

        except Exception as e:
            raise DocumentStorageException("Failed to generate a presigned URL.") from e

    async def list_documents(
            self,
            recursive: bool = True,
            prefix: Optional[str] = None
    ) -> list[dict[str, Any]]:
        try:
            full_prefix = self._build_prefix(prefix)
            objects = await self._minio_manager.list_objects(
                bucket_name=self._bucket_name,
                prefix=full_prefix,
                recursive=recursive
            )

            list_extra: dict[str, Any] = {
                "bucket": self._bucket_name,
                "count": len(objects)
            }
            if full_prefix:
                list_extra["prefix_suffix"] = full_prefix[-self._settings.list_prefix_log_suffix_chars:]
            logger.debug(
                "Documents were listed successfully.",
                extra=list_extra
            )
            return objects

        except Exception as e:
            raise DocumentStorageException("Failed to list documents.") from e

    async def health_check(
            self
    ) -> dict[str, Any]:
        try:
            minio_health = await self._minio_manager.health_check()
            minio_healthy = minio_health.get("status") == "healthy"

            bucket_accessible = False
            if minio_healthy:
                bucket_accessible = await self._probe_bucket_accessible()

            return {
                "status": "healthy" if (minio_healthy and bucket_accessible) else "unhealthy",
                "bucket": self._bucket_name,
                "bucket_accessible": bucket_accessible,
                "minio": minio_health
            }

        except Exception:
            logger.exception("Document storage health check failed.")
            return {
                "status": "unhealthy",
                "bucket": self._bucket_name,
                "error": "Health check failed; see application logs for details."
            }

    def _validate_file_size(self, file_size: int) -> None:
        if (self._settings.max_file_size_bytes is not None
                and file_size > self._settings.max_file_size_bytes):
            max_mb = self._settings.max_file_size_bytes / (1024 * 1024)
            raise DocumentSizeLimitException(f"File too large. Maximum allowed size: {max_mb:.1f} MB")

        if file_size < self._settings.min_file_size_bytes:
            raise DocumentSizeLimitException(
                f"File too small. Minimum size: {self._settings.min_file_size_bytes} bytes"
            )

    def _build_prefix(
            self,
            extra_prefix: Optional[str]
    ) -> Optional[str]:
        parts = []
        if self._settings.object_key_prefix:
            parts.append(self._settings.object_key_prefix)
        if extra_prefix:
            parts.append(extra_prefix.lstrip("/"))
        return "/".join(parts) if parts else None

    async def _probe_bucket_accessible(
            self
    ) -> bool:
        try:
            await self._minio_manager.object_exists(
                bucket_name=self._bucket_name,
                object_name=".health_probe"
            )
            return True
        except Exception as e:
            logger.warning(
                "The bucket accessibility probe failed.",
                extra={
                    "bucket": self._bucket_name,
                    "exception_type": type(e).__name__
                }
            )
            return False

    @staticmethod
    def _is_not_found_error(
            error: Exception
    ) -> bool:
        cause = getattr(error, "__cause__", None)
        return cause is not None and getattr(cause, "code", None) == "NoSuchKey"


async def get_document_storage(
        request: Request
) -> DocumentStorageInterface:
    try:
        return request.app.state.document_storage
    except AttributeError:
        logger.error("The document storage was not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is not configured"
        )
