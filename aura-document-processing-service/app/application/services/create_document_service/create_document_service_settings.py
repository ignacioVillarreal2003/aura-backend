import logging
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class CreateDocumentServiceSettings(BaseSettings):
    max_file_size_mb: int = Field(
        default=50,
        gt=0,
        le=500,
        description="Maximum file size in MB"
    )
    min_file_size_bytes: int = Field(
        default=1,
        gt=0,
        description="Minimum file size in bytes"
    )

    allowed_content_types: List[str] = Field(
        default=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "text/plain",
        ],
        description="List of allowed MIME types"
    )

    enable_background_processing: bool = Field(
        default=True,
        description="Enable background document processing"
    )
    cleanup_temp_files: bool = Field(
        default=True,
        description="Automatically cleanup temporary files after processing"
    )
    temp_dir_prefix: str = Field(
        default="doc_uploads",
        description="Prefix for temporary directory"
    )

    strict_validation: bool = Field(
        default=True,
        description="Enable strict validation (filename, content type, etc.)"
    )
    validate_file_content: bool = Field(
        default=False,
        description="Validate actual file content (slower but more secure)"
    )

    preserve_original_filename: bool = Field(
        default=True,
        description="Preserve original filename in storage"
    )
    generate_unique_names: bool = Field(
        default=True,
        description="Generate unique names to avoid collisions"
    )

    enable_metrics: bool = Field(
        default=True,
        description="Enable metrics collection"
    )

    @field_validator("max_file_size_mb")
    @classmethod
    def validate_max_file_size(
            cls,
            v: int
    ) -> int:
        if v < 1:
            raise ValueError("max_file_size_mb must be at least 1 MB")
        if v > 500:
            raise ValueError("max_file_size_mb cannot exceed 500 MB")
        return v

    @field_validator("allowed_content_types")
    @classmethod
    def validate_content_types(
            cls,
            v: List[str]
    ) -> List[str]:
        if not v:
            raise ValueError("allowed_content_types cannot be empty")

        normalized = [ct.lower().strip() for ct in v]

        if len(normalized) != len(set(normalized)):
            raise ValueError("allowed_content_types contains duplicates")

        return normalized

    @field_validator("temp_dir_prefix")
    @classmethod
    def validate_temp_dir_prefix(
            cls,
            v: str
    ) -> str:
        if not v or not v.strip():
            raise ValueError("temp_dir_prefix cannot be empty")

        v = v.strip()

        if '/' in v or '\\' in v:
            raise ValueError("temp_dir_prefix cannot contain path separators")

        return v

    def is_content_type_allowed(
            self,
            content_type: str
    ) -> bool:
        return content_type.lower() in self.allowed_content_types

    @property
    def max_file_size_bytes(
            self
    ) -> int:
        return self.max_file_size_mb * 1024 * 1024
