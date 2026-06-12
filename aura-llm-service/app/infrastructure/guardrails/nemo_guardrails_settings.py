from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NemoGuardrailsSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="NEMO_GUARDRAILS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    enabled: bool = Field(default=False)

    fail_open: bool = Field(default=True)

    max_input_chars: int = Field(default=8_000, ge=200, le=100_000)

    blocked_message: str = Field(
        default=(
            "La consulta fue bloqueada por el filtro de seguridad. "
            "Reformulá el mensaje en relación con los documentos o tareas del sistema."
        )
    )
