import logging
from typing import Optional

import unicodedata
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class DocumentStorageSettings(BaseSettings):
    bucket_name: str = Field(
        default="documents",
        description="Bucket name for document storage"
    )

    use_uuid_prefix: bool = Field(
        default=True,
        description="Use UUID prefixes for organizing documents"
    )
    path_prefix: Optional[str] = Field(
        default="documents",
        description="Prefix for all document paths (e.g., 'documents/', 'files/')"
    )
    organize_by_date: bool = Field(
        default=True,
        description="Organize documents by date (YYYY/MM/DD structure)"
    )

    preserve_original_filename: bool = Field(
        default=False,
        description="Preserve original filename in object name"
    )
    max_filename_length: int = Field(
        default=255,
        gt=0,
        le=1024,
        description="Maximum length for generated filenames"
    )
    allowed_extensions: Optional[list[str]] = Field(
        default=["pdf", "doc", "docx"],
        description="List of allowed file extensions (None = allow all)"
    )

    max_file_size: Optional[int] = Field(
        default=100 * 1024 * 1024,
        gt=0,
        description="Maximum file size in bytes (None = no limit)"
    )
    min_file_size: int = Field(
        default=1,
        gt=0,
        description="Minimum file size in bytes"
    )

    store_metadata: bool = Field(
        default=False,
        description="Store additional metadata with documents"
    )
    include_content_type: bool = Field(
        default=True,
        description="Include content type in object metadata"
    )

    default_presigned_url_expiry: int = Field(
        default=3600,
        gt=0,
        le=604800,
        description="Default expiry for presigned URLs in seconds"
    )

    enable_metrics: bool = Field(
        default=True,
        description="Enable operation metrics tracking"
    )
    auto_create_bucket: bool = Field(
        default=True,
        description="Automatically create bucket on start"
    )

    @field_validator("bucket_name")
    @classmethod
    def validate_bucket_name(
            cls,
            v: str
    ) -> str:
        if not v or not v.strip():
            raise ValueError("Bucket name cannot be empty")

        v = v.strip()

        if len(v) < 3 or len(v) > 63:
            raise ValueError(
                f"Bucket name must be between 3 and 63 characters, got: {len(v)}"
            )

        if not v.islower():
            raise ValueError("Bucket name must be lowercase")

        if not v[0].isalnum() or not v[-1].isalnum():
            raise ValueError("Bucket name must start and end with letter or number")

        import re
        if not re.match(r'^[a-z0-9][a-z0-9.-]*[a-z0-9]$', v):
            raise ValueError(
                "Bucket name can only contain lowercase letters, numbers, dots, and hyphens"
            )

        if '..' in v or '.-' in v or '-.' in v:
            raise ValueError("Bucket name cannot contain consecutive special characters")

        return v

    @field_validator("path_prefix")
    @classmethod
    def validate_path_prefix(
            cls,
            v: Optional[str]
    ) -> Optional[str]:
        if v is None:
            return v

        v = v.strip()
        if not v:
            return None

        v = v.strip('/')

        if not all(c.isalnum() or c in ['/', '-', '_'] for c in v):
            raise ValueError(
                "Path prefix can only contain alphanumeric characters, slashes, hyphens, and underscores"
            )

        return v

    @field_validator("allowed_extensions")
    @classmethod
    def validate_allowed_extensions(
            cls,
            v: Optional[list[str]]
    ) -> Optional[list[str]]:
        if v is None:
            return v

        normalized = []
        for ext in v:
            ext = ext.strip().lower()
            ext = ext.lstrip('.')
            if ext:
                normalized.append(ext)

        return normalized if normalized else None

    def is_extension_allowed(
            self,
            filename: str
    ) -> bool:
        if self.allowed_extensions is None:
            return True

        from pathlib import Path
        ext = Path(filename).suffix.lower().lstrip('.')

        return ext in self.allowed_extensions

    def generate_object_name(
            self,
            original_filename: str,
            document_id: Optional[str] = None
    ) -> str:
        from pathlib import Path
        from datetime import datetime
        import uuid

        ext = Path(original_filename).suffix

        parts = []

        if self.path_prefix:
            parts.append(self.path_prefix)

        if self.organize_by_date:
            now = datetime.utcnow()
            parts.extend([
                str(now.year),
                f"{now.month:02d}",
                f"{now.day:02d}"
            ])

        if self.preserve_original_filename:
            filename = Path(original_filename).stem
            filename = "".join(c for c in filename if c.isalnum() or c in ['-', '_'])
            filename = filename[:self.max_filename_length - len(ext)]
        else:
            filename = document_id if document_id else str(uuid.uuid4())

        if self.use_uuid_prefix and not document_id:
            filename = f"{uuid.uuid4().hex[:8]}_{filename}"

        object_name = "/".join(parts + [f"{filename}{ext}"])

        return object_name

    def sanitize_metadata_value(
            self,
            value: str
    ) -> str:
        return (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )