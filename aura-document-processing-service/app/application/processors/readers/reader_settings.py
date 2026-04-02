import logging
from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_SUPPORTED_TESSERACT_LANGS = frozenset({"spa", "eng", "spa+eng"})


class ReaderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="READER_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    docling_enabled: bool = Field(default=False)

    tesseract_path: Optional[str] = Field(default=None)
    tesseract_lang: str = Field(default="spa")
    tesseract_timeout: int = Field(default=300, ge=10, le=600)
    poppler_path: Optional[str] = Field(default=None)
    pdf_dpi: int = Field(default=300, ge=72, le=600)
    pdf_use_parallel: bool = Field(default=True)
    pdf_max_workers: Optional[int] = Field(default=None, ge=1, le=16)

    @model_validator(mode="after")
    def validate_reader_settings(self) -> "ReaderSettings":
        if self.tesseract_path is not None:
            self._validate_tesseract()
        return self

    def _validate_tesseract(self) -> None:
        if self.tesseract_lang not in _SUPPORTED_TESSERACT_LANGS:
            raise ValueError(
                f"tesseract_lang must be one of {_SUPPORTED_TESSERACT_LANGS}, "
                f"got '{self.tesseract_lang}'"
            )

    @property
    def ocr_enabled(self) -> bool:
        return self.tesseract_path is not None
