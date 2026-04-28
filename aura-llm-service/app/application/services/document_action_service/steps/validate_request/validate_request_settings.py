from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ValidateActionRequestSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="VALIDATE_ACTION_REQUEST_",
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

    @model_validator(mode="after")
    def validate_instruction_length_range(self) -> "ValidateActionRequestSettings":
        if self.min_instruction_length > self.max_instruction_length:
            raise ValueError(
                f"min_instruction_length ({self.min_instruction_length}) must be "
                f"less than or equal to max_instruction_length ({self.max_instruction_length})"
            )
        return self
