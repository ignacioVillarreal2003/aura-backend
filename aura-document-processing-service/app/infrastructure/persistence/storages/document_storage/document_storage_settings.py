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

_BUCKET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]*[a-z0-9]$")
_BUCKET_INVALID_CONSECUTIVE_RE = re.compile(r"\.\.|\.[-]|[-]\.")
_OBJECT_KEY_PREFIX_RE = re.compile(r"^[a-zA-Z0-9/_-]+$")
_METADATA_USER_KEY_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


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

    allowed_file_extensions: Optional[list[str]] = Field(
        default=[
            "pdf", "doc", "docx",
            "pptx", "xlsx",
            "txt", "md", "csv",
            "png", "jpg", "jpeg", "tiff", "tif", "bmp", "webp",
        ]
    )
    max_file_size_bytes: Optional[int] = Field(default=100 * 1024 * 1024, gt=0)
    min_file_size_bytes: int = Field(default=1, gt=0)

    attach_metadata_to_objects: bool = Field(default=False)
    send_content_type_header: bool = Field(default=True)

    max_additional_metadata_entries: int = Field(default=16, ge=0, le=64)
    max_metadata_key_length: int = Field(default=128, ge=8, le=256)
    max_metadata_value_length: int = Field(default=256, ge=16, le=1024)

    presigned_url_expiry_seconds: int = Field(default=3600, gt=0, le=604_800)

    object_key_log_suffix_chars: int = Field(default=48, ge=1, le=512)
    file_path_log_suffix_chars: int = Field(default=48, ge=1, le=512)
    list_prefix_log_suffix_chars: int = Field(default=32, ge=1, le=512)

    @field_validator(
        "bucket_name",
        mode="before"
    )
    @classmethod
    def validate_bucket_name(
            cls,
            v: str
    ) -> str:
        v = v.strip()

        if not (3 <= len(v) <= 63):
            raise ValueError("The bucket name length must be between 3 and 63 characters.")

        if not _BUCKET_NAME_RE.match(v):
            raise ValueError(
                "Use only lowercase letters, numbers, dots, and hyphens in the bucket name, "
                "and start and end with a letter or number."
            )

        if _BUCKET_INVALID_CONSECUTIVE_RE.search(v):
            raise ValueError("The bucket name cannot use consecutive dots or mix dots and hyphens in invalid ways.")

        return v

    @field_validator(
        "object_key_prefix",
        mode="before"
    )
    @classmethod
    def validate_object_key_prefix(
            cls,
            v: Optional[str]
    ) -> Optional[str]:
        if v is None:
            return v

        v = v.strip().strip("/")
        if not v:
            return None

        if not _OBJECT_KEY_PREFIX_RE.match(v):
            raise ValueError("The object key prefix may only use letters, numbers, slashes, hyphens, and underscores.")

        return v

    @field_validator(
        "allowed_file_extensions",
        mode="before"
    )
    @classmethod
    def normalise_allowed_file_extensions(
            cls,
            v: Optional[list[str]]
    ) -> Optional[list[str]]:
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

    @model_validator(
        mode="after"
    )
    def validate_coherence(
            self
    ) -> "DocumentStorageSettings":
        if (self.max_file_size_bytes is not None
                and self.min_file_size_bytes >= self.max_file_size_bytes):
            raise ValueError("The minimum file size must be less than the maximum file size.")
        return self

    def build_upload_object_metadata(
            self,
            original_filename: str,
            document_id: Optional[str],
            additional_metadata: Optional[dict[str, str]],
            upload_timestamp_seconds: int,
    ) -> Optional[dict[str, str]]:
        if not self.attach_metadata_to_objects:
            return None

        metadata: dict[str, str] = {
            "original_filename": self.sanitize_metadata_value(original_filename),
            "document_id": self.sanitize_metadata_value(document_id or "none"),
            "upload_timestamp": str(int(upload_timestamp_seconds)),
        }
        if additional_metadata:
            metadata.update(self._normalize_user_metadata_dict(additional_metadata))
        return metadata

    def _normalize_user_metadata_dict(
            self,
            raw: dict[str, str],
    ) -> dict[str, str]:
        if len(raw) > self.max_additional_metadata_entries:
            raise ValueError(
                f"Too many additional metadata entries (maximum {self.max_additional_metadata_entries})."
            )

        out: dict[str, str] = {}
        for raw_key, raw_val in raw.items():
            key = raw_key.strip()
            if not key:
                raise ValueError("Metadata keys cannot be empty or whitespace-only.")
            if len(key) > self.max_metadata_key_length:
                raise ValueError("A metadata key exceeds the configured maximum length.")
            if not _METADATA_USER_KEY_RE.match(key):
                raise ValueError(
                    "Metadata keys may only contain letters, numbers, underscores, and hyphens."
                )

            value = self.sanitize_metadata_value(raw_val)
            if len(value) > self.max_metadata_value_length:
                raise ValueError("A metadata value exceeds the configured maximum length after sanitization.")

            out[key] = value

        return out

    def is_extension_allowed(
            self,
            filename: str
    ) -> bool:
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

        unique_suffix = uuid.uuid4().hex
        if document_id:
            sanitized_document_id = "".join(c for c in document_id if c.isalnum() or c in ("-", "_")) or "doc"
            stem = f"{sanitized_document_id}_{unique_suffix[:12]}"
        elif self.preserve_original_filename_as_stem:
            raw_stem = Path(original_filename).stem
            sanitised = "".join(c for c in raw_stem if c.isalnum() or c in ("-", "_"))
            max_stem = max(0, self.max_object_stem_length - len(ext))
            sanitised = sanitised[:max_stem] or uuid.uuid4().hex
            if self.uuid_prefix_on_preserved_stem:
                stem = f"{unique_suffix[:8]}_{sanitised}"
            else:
                stem = f"{sanitised}_{unique_suffix[:8]}"
        else:
            stem = unique_suffix

        return "/".join([*parts, f"{stem}{ext}"])

    @staticmethod
    def sanitize_metadata_value(
            value: str
    ) -> str:
        return (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
