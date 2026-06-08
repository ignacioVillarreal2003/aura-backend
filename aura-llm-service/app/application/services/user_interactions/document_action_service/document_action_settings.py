from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentActionServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_ACTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_document_ids: int = Field(default=10, ge=1, le=50)
    min_document_id: int = Field(default=1, ge=1)
    max_document_id: int = Field(default=2_147_483_647, ge=1)
    min_instruction_length: int = Field(default=3, ge=1)
    max_instruction_length: int = Field(default=2000, ge=1, le=10_000)

    large_document_threshold: int = Field(default=10, ge=2, le=100)

    chunk_size: int = Field(default=5, ge=1, le=20)
    max_concurrent_chunks: int = Field(default=3, ge=1, le=10)
    max_retry_attempts: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=1.0, ge=0.0, le=60.0)

    @model_validator(mode="after")
    def validate_instruction_length_range(self) -> "DocumentActionServiceSettings":
        if self.min_instruction_length > self.max_instruction_length:
            raise ValueError(
                f"min_instruction_length ({self.min_instruction_length}) must be "
                f"less than or equal to max_instruction_length ({self.max_instruction_length})"
            )
        return self
