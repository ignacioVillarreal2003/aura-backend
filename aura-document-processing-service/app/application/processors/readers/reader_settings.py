import logging
from typing import Optional
from pydantic import Field, field_validator
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

    tesseract_path: Optional[str] = Field(
        default=None
    )
    tesseract_lang: str = Field(
        default="spa"
    )
    tesseract_timeout: int = Field(
        default=300,
        ge=10,
        le=600
    )

    poppler_path: Optional[str] = Field(
        default=None
    )

    pdf_dpi: int = Field(
        default=300,
        ge=72,
        le=600
    )
    pdf_use_parallel: bool = Field(
        default=True
    )
    pdf_max_workers: Optional[int] = Field(
        default=None,
        ge=1,
        le=16
    )

    @field_validator(
        "tesseract_lang"
    )
    @classmethod
    def validate_tesseract_lang(
            cls,
            v: str
    ) -> str:
        supported_tesseract_langs = ["spa", "eng"]
        if v not in supported_tesseract_langs:
            raise ValueError(f"tesseract_lang must be one of {supported_tesseract_langs}, got '{v}'")
        return v
