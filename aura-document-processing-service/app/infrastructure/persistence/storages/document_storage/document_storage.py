import asyncio
import logging
import time
from pathlib import Path
from typing import Any, AsyncIterator, Optional
from fastapi import HTTPException, Request, status, UploadFile
from minio.error import S3Error

from app.application.exceptions.app_exception import AppException
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
    MinioDownloadException,
    MinioManagerException,
)
from app.infrastructure.persistence.storages.minio_manager.interfaces.minio_manager_interface import (
    MinioManagerInterface
)

logger = logging.getLogger(__name__)


def _validate_object_storage_key_fragment(value: str, *, label: str) -> None:
    if "\x00" in value:
        raise DocumentValidationException(f"Invalid {label}: null bytes are not allowed.")
    if ".." in value:
        raise DocumentValidationException(f"Invalid {label}: parent-directory segments are not allowed.")


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

        except asyncio.CancelledError:
            raise
        except (MinioManagerException, OSError) as e:
            raise DocumentStorageException("Failed to start document storage.") from e
        except Exception:
            logger.exception("Document storage failed to start with an unexpected error.")
            raise

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

            try:
                metadata = self._settings.build_upload_object_metadata(
                    original_filename=file.filename,
                    document_id=document_id,
                    additional_metadata=additional_metadata,
                    upload_timestamp_seconds=int(time.time()),
                )
            except ValueError as e:
                raise DocumentValidationException(str(e)) from e

            await self._minio_manager.upload_data(
                bucket_name=self._bucket_name,
                object_name=object_name,
                data=content,
                content_type=(
                    file.content_type if self._settings.send_content_type_header else None
                ),
                metadata=metadata,
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
                DocumentSizeLimitException,
        ):
            raise

        except asyncio.CancelledError:
            raise

        except (MinioManagerException, OSError) as e:
            raise DocumentUploadException("Failed to upload the document.") from e

        except AppException:
            raise

        except Exception:
            logger.exception("Failed to upload the document (unexpected error).")
            raise

    async def upload_document_from_path(
            self,
            file_path: str,
            original_filename: str,
            document_id: Optional[str] = None,
            additional_metadata: Optional[dict[str, str]] = None,
            content_type: Optional[str] = None,
    ) -> str:
        start_time = time.monotonic()
        try:
            if not original_filename:
                raise DocumentValidationException("Filename cannot be empty.")
            if "\x00" in file_path:
                raise DocumentValidationException("Invalid file path: null bytes are not allowed.")
            if not self._settings.is_extension_allowed(original_filename):
                allowed = (
                    ", ".join(self._settings.allowed_file_extensions)
                    if self._settings.allowed_file_extensions
                    else "all"
                )
                raise DocumentExtensionException(f"File extension not allowed. Permitted: {allowed}")

            file_size = Path(file_path).stat().st_size
            self._validate_file_size(file_size)
            object_name = self._settings.generate_object_name(
                original_filename=original_filename,
                document_id=document_id,
            )
            try:
                metadata = self._settings.build_upload_object_metadata(
                    original_filename=original_filename,
                    document_id=document_id,
                    additional_metadata=additional_metadata,
                    upload_timestamp_seconds=int(time.time()),
                )
            except ValueError as e:
                raise DocumentValidationException(str(e)) from e

            await self._minio_manager.upload_file(
                bucket_name=self._bucket_name,
                object_name=object_name,
                file_path=file_path,
                content_type=(content_type if self._settings.send_content_type_header else None),
                metadata=metadata,
            )
            elapsed_ms = round((time.monotonic() - start_time) * 1000, 2)
            logger.info(
                "The document was uploaded from file path successfully.",
                extra={
                    "bucket": self._bucket_name,
                    "object_key_suffix": object_name[-self._settings.object_key_log_suffix_chars:] if object_name else "",
                    "size_bytes": file_size,
                    "elapsed_ms": elapsed_ms,
                },
            )
            return object_name
        except (DocumentValidationException, DocumentExtensionException, DocumentSizeLimitException):
            raise
        except asyncio.CancelledError:
            raise
        except (MinioManagerException, OSError) as e:
            raise DocumentUploadException("Failed to upload the document.") from e
        except AppException:
            raise
        except Exception:
            logger.exception("Failed to upload the document from file path (unexpected error).")
            raise

    async def download_document(
            self,
            object_name: str
    ) -> bytes:
        start_time = time.monotonic()

        try:
            _validate_object_storage_key_fragment(object_name, label="object name")

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

        except asyncio.CancelledError:
            raise

        except (MinioManagerException, OSError) as e:
            raise DocumentDownloadException("Failed to download the document.") from e

        except AppException:
            raise

        except Exception:
            logger.exception("Failed to download the document (unexpected error).")
            raise

    async def download_document_stream(
            self,
            object_name: str,
            chunk_size: int,
    ) -> AsyncIterator[bytes]:
        try:
            _validate_object_storage_key_fragment(object_name, label="object name")
            async for chunk in self._minio_manager.download_data_stream(
                    bucket_name=self._bucket_name,
                    object_name=object_name,
                    chunk_size=chunk_size,
            ):
                yield chunk
        except MinioDownloadException as e:
            if self._is_not_found_error(e):
                raise DocumentNotFoundException("The document was not found.") from e
            raise DocumentDownloadException("Failed to download the document.") from e
        except asyncio.CancelledError:
            raise
        except (MinioManagerException, OSError) as e:
            raise DocumentDownloadException("Failed to download the document.") from e
        except AppException:
            raise
        except Exception:
            logger.exception("Failed to stream the document (unexpected error).")
            raise

    async def download_document_to_file(
            self,
            object_name: str,
            file_path: str
    ) -> None:
        start_time = time.monotonic()

        try:
            _validate_object_storage_key_fragment(object_name, label="object name")
            if "\x00" in file_path:
                raise DocumentValidationException("Invalid file path: null bytes are not allowed.")

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

        except asyncio.CancelledError:
            raise

        except (MinioManagerException, OSError) as e:
            raise DocumentDownloadException("Failed to download the document.") from e

        except AppException:
            raise

        except Exception:
            logger.exception("Failed to download the document to file (unexpected error).")
            raise

    async def delete_document(self, object_name: str) -> None:
        try:
            _validate_object_storage_key_fragment(object_name, label="object name")

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

        except asyncio.CancelledError:
            raise

        except (MinioManagerException, OSError) as e:
            raise DocumentDeleteException("Failed to delete the document.") from e

        except AppException:
            raise

        except Exception:
            logger.exception("Failed to delete the document (unexpected error).")
            raise

    async def document_exists(
            self,
            object_name: str
    ) -> bool:
        try:
            _validate_object_storage_key_fragment(object_name, label="object name")

            return await self._minio_manager.object_exists(
                bucket_name=self._bucket_name,
                object_name=object_name
            )
        except asyncio.CancelledError:
            raise

        except S3Error as e:
            raise DocumentStorageException("Failed to check whether the document exists.") from e

        except (MinioManagerException, OSError) as e:
            raise DocumentStorageException("Failed to check whether the document exists.") from e

        except AppException:
            raise

        except Exception:
            logger.exception("Failed to check whether the document exists (unexpected error).")
            raise

    async def get_presigned_url(
            self,
            object_name: str,
            method: str = "GET",
            expires: Optional[int] = None
    ) -> str:
        expiry = expires if expires is not None else self._settings.presigned_url_expiry_seconds

        try:
            _validate_object_storage_key_fragment(object_name, label="object name")

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

        except asyncio.CancelledError:
            raise

        except (MinioManagerException, OSError) as e:
            raise DocumentStorageException("Failed to generate a presigned URL.") from e

        except AppException:
            raise

        except Exception:
            logger.exception("Failed to generate a presigned URL (unexpected error).")
            raise

    async def list_documents(
            self,
            recursive: bool = True,
            prefix: Optional[str] = None
    ) -> list[dict[str, Any]]:
        try:
            if prefix is not None:
                _validate_object_storage_key_fragment(prefix, label="list prefix")

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

        except asyncio.CancelledError:
            raise

        except (MinioManagerException, OSError) as e:
            raise DocumentStorageException("Failed to list documents.") from e

        except AppException:
            raise

        except Exception:
            logger.exception("Failed to list documents (unexpected error).")
            raise

    async def health_check(
            self,
            detailed: bool = False,
    ) -> dict[str, Any]:
        start_time = time.monotonic()
        try:
            minio_health = await self._minio_manager.health_check(detailed=detailed)
            minio_healthy = minio_health.get("status") == "healthy"

            bucket_accessible = False
            if minio_healthy:
                bucket_accessible = await self._probe_bucket_accessible()

            latency_ms = round((time.monotonic() - start_time) * 1000, 2)
            overall_ok = minio_healthy and bucket_accessible

            if not detailed:
                return {
                    "status": "healthy" if overall_ok else "unhealthy",
                    "latency_ms": latency_ms,
                    "bucket_accessible": bucket_accessible,
                }

            return {
                "status": "healthy" if overall_ok else "unhealthy",
                "latency_ms": latency_ms,
                "bucket": self._bucket_name,
                "bucket_accessible": bucket_accessible,
                "minio": minio_health,
            }

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Document storage health check failed.")
            latency_ms = round((time.monotonic() - start_time) * 1000, 2)
            err: dict[str, Any] = {
                "status": "unhealthy",
                "latency_ms": latency_ms,
                "bucket_accessible": False,
                "error": "Health check failed; see application logs for details.",
            }
            if detailed:
                err["bucket"] = self._bucket_name
            return err

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
        except asyncio.CancelledError:
            raise
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
        visited: set[int] = set()
        current: Optional[BaseException] = error
        while current is not None and id(current) not in visited:
            visited.add(id(current))
            if getattr(current, "code", None) == "NoSuchKey":
                return True
            current = current.__cause__ or current.__context__
        return False


async def get_document_storage(
        request: Request
) -> DocumentStorageInterface:
    document_storage = getattr(request.app.state, "document_storage", None)
    if document_storage is None:
        logger.error("The document storage was not registered on the application state.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is not configured"
        )
    return document_storage
