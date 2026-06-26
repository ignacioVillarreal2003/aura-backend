import logging
from pathlib import Path
from typing import Optional, Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class ReaderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="READER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    tesseract_path: Optional[str] = Field(default=None)
    tesseract_lang: Literal["spa", "eng", "spa+eng"] = "spa"
    tesseract_timeout: int = Field(default=300, ge=10, le=600)
    poppler_path: Optional[str] = Field(default=None)
    pdf_dpi: int = Field(default=300, ge=72, le=600)
    pdf_use_parallel: bool = Field(default=True)
    pdf_max_workers: Optional[int] = Field(default=None, ge=1, le=16)
    pdf_max_ocr_pages: int = Field(default=500, ge=1, le=5_000)

    docling_enabled: bool = Field(default=True)
    docling_device: Literal["cpu", "cuda", "mps", "auto"] = "auto"
    docling_num_threads: int = Field(default=4, ge=1, le=16)
    docling_artifacts_path: Optional[str] = Field(default=None)

    @model_validator(
        mode="after"
    )
    def validate_reader_settings(
            self
    ) -> "ReaderSettings":
        self.tesseract_path = self._normalize_optional_path(self.tesseract_path)
        self.poppler_path = self._normalize_optional_path(self.poppler_path)
        self.docling_artifacts_path = self._normalize_optional_path(self.docling_artifacts_path)

        if self.tesseract_path is not None:
            self._validate_existing_path(self.tesseract_path, "tesseract_path", should_be_file=True)

        if self.poppler_path is not None:
            self._validate_existing_path(self.poppler_path, "poppler_path", should_be_file=False)

        if self.docling_artifacts_path is not None:
            self._validate_existing_path(
                self.docling_artifacts_path, "docling_artifacts_path", should_be_file=False
            )

        if self.pdf_use_parallel and self.pdf_max_workers == 1:
            self.pdf_use_parallel = False

        if self.docling_enabled and self.docling_num_threads < 1:
            raise ValueError("docling_num_threads must be at least 1 when docling is enabled.")

        return self

    @property
    def ocr_enabled(
            self
    ) -> bool:
        return self.tesseract_path is not None

    @staticmethod
    def _normalize_optional_path(path: Optional[str]) -> Optional[str]:
        if path is None:
            return None
        normalized = path.strip()
        return normalized or None

    @staticmethod
    def _validate_existing_path(path: str, field_name: str, *, should_be_file: bool) -> None:
        candidate = Path(path)
        if not candidate.exists():
            raise ValueError(f"{field_name} does not exist: {path}")
        if should_be_file and not candidate.is_file():
            raise ValueError(f"{field_name} must point to a file: {path}")
        if not should_be_file and not candidate.is_dir():
            raise ValueError(f"{field_name} must point to a directory: {path}")
