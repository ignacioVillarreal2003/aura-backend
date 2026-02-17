import logging
import time
from typing import Optional, Dict, Any, List
from fastapi import UploadFile

from app.infrastructure.persistence.storages.document_storage.document_storage_settings import DocumentStorageSettings
from app.infrastructure.persistence.storages.document_storage.exceptions.document_storage_exception import (
    DocumentStorageError,
    DocumentUploadError,
    DocumentDownloadError,
    DocumentDeleteError,
    DocumentValidationError
)
from app.infrastructure.persistence.storages.document_storage.interfaces.document_storage_interface import (
    DocumentStorageInterface
)
from app.infrastructure.persistence.storages.minio_manager.interfaces.minio_manager_interface import (
    MinioManagerInterface
)

logger = logging.getLogger(__name__)


class DocumentStorage(DocumentStorageInterface):
    def __init__(
            self,
            minio_manager: MinioManagerInterface,
            document_storage_settings: DocumentStorageSettings
    ):
        self._minio_manager = minio_manager
        self._document_storage_settings = document_storage_settings
        self._bucket_name = document_storage_settings.bucket_name

        self._upload_count = 0
        self._download_count = 0
        self._delete_count = 0
        self._error_count = 0
        self._bytes_uploaded = 0
        self._bytes_downloaded = 0

    @classmethod
    def create(
            cls,
            minio_manager: MinioManagerInterface,
            bucket_name: Optional[str] = None,
            **config_kwargs
    ) -> "DocumentStorage":
        if bucket_name:
            config_kwargs['bucket_name'] = bucket_name

        document_storage_settings = DocumentStorageSettings(
            **config_kwargs
        )

        return cls(
            minio_manager=minio_manager,
            document_storage_settings=document_storage_settings
        )

    async def start(
            self
    ) -> None:
        try:
            if self._document_storage_settings.auto_create_bucket:
                logger.info(f"Ensuring bucket exists: {self._bucket_name}")
                await self._minio_manager.ensure_bucket(self._bucket_name)

            logger.info("DocumentStorage started successfully")

        except Exception as e:
            logger.exception("Failed to start DocumentStorage")
            raise DocumentStorageError(f"Failed to start DocumentStorage: {str(e)}") from e

    def _validate_file(
            self,
            file: UploadFile
    ) -> None:
        if not file.filename:
            raise DocumentValidationError("Filename cannot be empty")

        if not self._document_storage_settings.is_extension_allowed(file.filename):
            allowed = ", ".join(
                self._document_storage_settings.allowed_extensions) if self._document_storage_settings.allowed_extensions else "all"
            raise DocumentValidationError(f"File extension not allowed. Allowed extensions: {allowed}")

        if file.size is not None:
            if self._document_storage_settings.max_file_size and file.size > self._document_storage_settings.max_file_size:
                max_mb = self._document_storage_settings.max_file_size / (1024 * 1024)
                raise DocumentValidationError(f"File too large. Maximum size: {max_mb:.2f} MB")

            if file.size < self._document_storage_settings.min_file_size:
                raise DocumentValidationError(
                    f"File too small. Minimum size: {self._document_storage_settings.min_file_size} bytes"
                )

    async def upload_document(
            self,
            file: UploadFile,
            document_id: Optional[str] = None,
            additional_metadata: Optional[Dict[str, str]] = None
    ) -> str:
        start_time = time.time()

        try:
            self._validate_file(file)

            object_name = self._document_storage_settings.generate_object_name(
                original_filename=file.filename,
                document_id=document_id
            )

            content = await file.read()
            file_size = len(content)

            metadata = {}
            if self._document_storage_settings.store_metadata:
                metadata["original_filename"] = self._document_storage_settings.sanitize_metadata_value(file.filename)
                metadata["document_id"] = document_id if document_id else "none"
                metadata["upload_timestamp"] = str(int(time.time()))

                if additional_metadata:
                    metadata.update(additional_metadata)

            await self._minio_manager.upload_data(
                bucket_name=self._bucket_name,
                object_name=object_name,
                data=content,
                content_type=file.content_type if self._document_storage_settings.include_content_type else None,
                metadata=metadata if metadata else None
            )

            self._upload_count += 1
            self._bytes_uploaded += file_size

            elapsed = (time.time() - start_time) * 1000

            logger.info(
                "Document uploaded successfully",
                extra={
                    "object_name": object_name,
                    "document_filename": file.filename,
                    "size_bytes": file_size,
                    "elapsed_ms": round(elapsed, 2)
                }
            )

            return object_name

        except DocumentValidationError:
            self._error_count += 1
            raise

        except Exception as e:
            self._error_count += 1
            logger.exception("Failed to upload document")
            raise DocumentUploadError(f"Failed to upload document: {str(e)}") from e

    async def download_document(
            self,
            object_name: str
    ) -> bytes:
        start_time = time.time()

        try:
            content = await self._minio_manager.download_data(
                bucket_name=self._bucket_name,
                object_name=object_name
            )

            self._download_count += 1
            self._bytes_downloaded += len(content)

            elapsed = (time.time() - start_time) * 1000

            logger.info(
                "Document downloaded successfully",
                extra={
                    "object_name": object_name,
                    "size_bytes": len(content),
                    "elapsed_ms": round(elapsed, 2)
                }
            )

            return content

        except Exception as e:
            self._error_count += 1
            logger.exception("Failed to download document")
            raise DocumentDownloadError(f"Failed to download document: {str(e)}") from e

    async def download_document_to_file(
            self,
            object_name: str,
            file_path: str
    ) -> None:
        try:
            await self._minio_manager.download_file(
                bucket_name=self._bucket_name,
                object_name=object_name,
                file_path=file_path
            )

            self._download_count += 1

            logger.info(
                "Document downloaded to file",
                extra={
                    "object_name": object_name,
                    "file_path": file_path
                }
            )

        except Exception as e:
            self._error_count += 1
            logger.exception("Failed to download document to file")
            raise DocumentDownloadError(f"Failed to download document to file: {str(e)}") from e

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

        except Exception as e:
            self._error_count += 1
            logger.exception("Failed to delete document")
            raise DocumentDeleteError(f"Failed to delete document: {str(e)}") from e

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
            logger.exception("Error checking document existence")
            raise DocumentStorageError(f"Failed to check document existence: {str(e)}") from e

    async def get_presigned_url(
            self,
            object_name: str,
            expires: Optional[int] = None,
            method: str = "GET"
    ) -> str:
        try:
            if expires is None:
                expires = self._document_storage_settings.default_presigned_url_expiry

            url = await self._minio_manager.get_presigned_url(
                bucket_name=self._bucket_name,
                object_name=object_name,
                expires=expires,
                method=method
            )

            logger.debug(
                "Presigned URL generated",
                extra={
                    "object_name": object_name,
                    "expires": expires,
                    "method": method
                }
            )

            return url

        except Exception as e:
            logger.exception("Failed to generate presigned URL")
            raise DocumentStorageError(f"Failed to generate presigned URL: {str(e)}") from e

    async def list_documents(
            self,
            prefix: Optional[str] = None,
            recursive: bool = True
    ) -> List[Dict[str, Any]]:
        try:
            full_prefix = None
            if self._document_storage_settings.path_prefix or prefix:
                parts = []
                if self._document_storage_settings.path_prefix:
                    parts.append(self._document_storage_settings.path_prefix)
                if prefix:
                    parts.append(prefix.lstrip('/'))
                full_prefix = "/".join(parts)

            objects = await self._minio_manager.list_objects(
                bucket_name=self._bucket_name,
                prefix=full_prefix,
                recursive=recursive
            )

            logger.debug(
                f"Listed {len(objects)} documents",
                extra={
                    "prefix": full_prefix,
                    "count": len(objects)
                }
            )

            return objects

        except Exception as e:
            logger.exception("Failed to list documents")
            raise DocumentStorageError(f"Failed to list documents: {str(e)}") from e

    async def health_check(
            self
    ) -> Dict[str, Any]:
        try:
            minio_health = await self._minio_manager.health_check()

            bucket_accessible = await self._minio_manager.object_exists(
                bucket_name=self._bucket_name,
                object_name=".health_check"  # Dummy object
            ) if minio_health["status"] == "healthy" else False

            status = "healthy" if minio_health["status"] == "healthy" else "unhealthy"

            return {
                "status": status,
                "bucket": self._bucket_name,
                "bucket_accessible": bucket_accessible,
                "minio": minio_health,
                "metrics": self.get_metrics(),
                "timestamp": time.time()
            }

        except Exception as e:
            logger.exception("Health check failed")
            return {
                "status": "unhealthy",
                "bucket": self._bucket_name,
                "error": str(e),
                "timestamp": time.time()
            }

    def get_metrics(
            self
    ) -> Dict[str, int]:
        return {
            "upload_count": self._upload_count,
            "download_count": self._download_count,
            "delete_count": self._delete_count,
            "error_count": self._error_count,
            "bytes_uploaded": self._bytes_uploaded,
            "bytes_downloaded": self._bytes_downloaded,
        }
