import logging
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class CreateDocumentServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CREATE_DOCUMENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    max_file_size_mb: int = Field(default=50, ge=1, le=500)
    min_file_size_bytes: int = Field(default=1, ge=1)

    chunk_size_bytes: int = Field(default=65536, ge=4096, le=10_485_760)
    temp_dir_prefix: str = Field(default="doc_uploads")

    allowed_content_types: list[str] = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/markdown",
        "text/csv",
        "application/csv",
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/bmp",
        "image/webp",
    ]
    content_type_mapping: dict[str, str] = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "text/plain": "txt",
        "text/markdown": "md",
        "text/csv": "csv",
        "application/csv": "csv",
        "image/png": "png",
        "image/jpeg": "jpeg",
        "image/tiff": "tiff",
        "image/bmp": "bmp",
        "image/webp": "webp",
    }
    magic_number_validation: dict[str, list[bytes]] = {
        "application/pdf": [b"%PDF"],
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [
            b"PK\x03\x04",
            b"PK\x05\x06",
            b"PK\x07\x08",
        ],
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": [
            b"PK\x03\x04",
            b"PK\x05\x06",
            b"PK\x07\x08",
        ],
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [
            b"PK\x03\x04",
            b"PK\x05\x06",
            b"PK\x07\x08",
        ],
        "image/png": [b"\x89PNG"],
        "image/jpeg": [b"\xff\xd8\xff"],
        "image/tiff": [b"II*\x00", b"MM\x00*"],
        "image/bmp": [b"BM"],
        "image/webp": [b"RIFF"],
    }

    @field_validator(
        "allowed_content_types",
        mode="before"
    )
    @classmethod
    def validate_content_types(
            cls,
            v: list[str]
    ) -> list[str]:
        if not v:
            raise ValueError("allowed_content_types cannot be empty")
        normalised = [ct.lower().strip() for ct in v]
        if len(normalised) != len(set(normalised)):
            raise ValueError("allowed_content_types contains duplicates")
        return normalised

    @field_validator(
        "temp_dir_prefix",
        mode="before"
    )
    @classmethod
    def validate_temp_dir_prefix(
            cls,
            v: str
    ) -> str:
        v = v.strip()
        if not v:
            raise ValueError("temp_dir_prefix cannot be empty")
        if "/" in v or "\\" in v:
            raise ValueError("temp_dir_prefix cannot contain path separators")
        return v

    @model_validator(mode="after")
    def validate_coherence(
            self
    ) -> "CreateDocumentServiceSettings":
        if self.min_file_size_bytes >= self.max_file_size_bytes:
            raise ValueError(
                f"min_file_size_bytes ({self.min_file_size_bytes}) must be "
                f"less than max_file_size_bytes ({self.max_file_size_bytes})"
            )
        return self

    @property
    def max_file_size_bytes(
            self
    ) -> int:
        return self.max_file_size_mb * 1024 * 1024

    def is_content_type_allowed(
            self,
            content_type: str
    ) -> bool:
        return content_type.lower() in self.allowed_content_types

    def get_document_type(
            self,
            content_type: str
    ) -> str | None:
        return self.content_type_mapping.get(content_type.lower())

    def get_magic_numbers(
            self,
            content_type: str
    ) -> list[bytes]:
        return self.magic_number_validation.get(content_type.lower(), [])
