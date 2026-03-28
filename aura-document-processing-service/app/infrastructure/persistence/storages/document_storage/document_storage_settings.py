import logging
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class DocumentStorageSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_STORAGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    bucket_name: str = Field(default="documents")
    auto_create_bucket_if_missing: bool = Field(default=True)

    object_key_prefix: Optional[str] = Field(default="documents")
    organize_objects_by_date: bool = Field(default=True)
    preserve_original_filename_as_stem: bool = Field(default=False)
    uuid_prefix_on_preserved_stem: bool = Field(default=True)
    max_object_stem_length: int = Field(default=255, gt=0, le=1024)

    allowed_file_extensions: Optional[list[str]] = Field(default=["pdf", "doc", "docx"])
    max_file_size_bytes: Optional[int] = Field(default=100 * 1024 * 1024, gt=0)
    min_file_size_bytes: int = Field(default=1, gt=0)

    attach_metadata_to_objects: bool = Field(default=False)
    send_content_type_header: bool = Field(default=True)

    presigned_url_expiry_seconds: int = Field(default=3600, gt=0, le=604_800)

    @field_validator("bucket_name", mode="before")
    @classmethod
    def validate_bucket_name(cls, v: str) -> str:
        v = v.strip()

        if not (3 <= len(v) <= 63):
            raise ValueError(
                f"Bucket name must be between 3 and 63 characters, got {len(v)}"
            )

        _BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*[a-z0-9]$")
        if not _BUCKET_NAME_RE.match(v):
            raise ValueError(
                "Bucket name may only contain lowercase letters, numbers, hyphens and dots, "
                "and must start/end with a letter or number"
            )

        _BUCKET_INVALID_CONSECUTIVE_RE = re.compile(r"\.\.|\.[-]|[-]\.")
        if _BUCKET_INVALID_CONSECUTIVE_RE.search(v):
            raise ValueError(
                "Bucket name cannot contain consecutive special characters ('..', '.-', '-.')"
            )

        return v

    @field_validator("object_key_prefix", mode="before")
    @classmethod
    def validate_object_key_prefix(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v

        v = v.strip().strip("/")
        if not v:
            return None

        _OBJECT_KEY_PREFIX_RE = re.compile(r"^[a-zA-Z0-9/_-]+$")
        if not _OBJECT_KEY_PREFIX_RE.match(v):
            raise ValueError(
                "object_key_prefix may only contain alphanumeric characters, "
                "forward slashes, hyphens and underscores"
            )

        return v

    @field_validator("allowed_file_extensions", mode="before")
    @classmethod
    def normalise_allowed_file_extensions(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None

        if isinstance(v, str):
            v = v.split(",")

        normalised = [
            ext.strip().lower().lstrip(".")
            for ext in v
            if ext.strip().lstrip(".")
        ]
        return normalised or None

    @model_validator(mode="after")
    def validate_coherence(self) -> "DocumentStorageSettings":
        if (self.max_file_size_bytes is not None
                and self.min_file_size_bytes >= self.max_file_size_bytes):
            raise ValueError(
                f"min_file_size_bytes ({self.min_file_size_bytes}) must be "
                f"less than max_file_size_bytes ({self.max_file_size_bytes})"
            )
        return self

    def is_extension_allowed(self, filename: str) -> bool:
        if self.allowed_file_extensions is None:
            return True
        ext = Path(filename).suffix.lower().lstrip(".")
        return ext in self.allowed_file_extensions

    def generate_object_name(
            self,
            original_filename: str,
            document_id: Optional[str] = None
    ) -> str:
        ext = Path(original_filename).suffix
        parts: list[str] = []

        if self.object_key_prefix:
            parts.append(self.object_key_prefix)

        if self.organize_objects_by_date:
            now = datetime.now(timezone.utc)
            parts += [str(now.year), f"{now.month:02d}", f"{now.day:02d}"]

        if document_id:
            stem = document_id
        elif self.preserve_original_filename_as_stem:
            raw_stem = Path(original_filename).stem
            sanitised = "".join(c for c in raw_stem if c.isalnum() or c in ("-", "_"))
            max_stem = max(0, self.max_object_stem_length - len(ext))
            sanitised = sanitised[:max_stem] or uuid.uuid4().hex
            stem = (
                f"{uuid.uuid4().hex[:8]}_{sanitised}"
                if self.uuid_prefix_on_preserved_stem
                else sanitised
            )
        else:
            stem = str(uuid.uuid4())

        return "/".join(parts + [f"{stem}{ext}"])

    @staticmethod
    def sanitize_metadata_value(value: str) -> str:
        return (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
