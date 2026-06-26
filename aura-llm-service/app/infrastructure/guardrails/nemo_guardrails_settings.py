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

    enabled: bool = Field(default=True)

    fail_open: bool = Field(default=True)

    check_output: bool = Field(default=False)

    max_input_chars: int = Field(default=8_000, ge=200, le=100_000)
    max_output_chars: int = Field(default=8_000, ge=200, le=100_000)

    check_timeout_seconds: float = Field(default=5.0, gt=0.0, le=60.0)

    blocked_output_message: str = Field(
        default=(
            "La respuesta fue retenida por el filtro de seguridad. "
            "Reformulá la consulta en relación con los documentos o tareas del sistema."
        )
    )

    blocked_message: str = Field(
        default=(
            "No se pudo procesar tu consulta porque no está relacionada con los "
            "documentos o las tareas del sistema. Reformulá el mensaje en relación "
            "con tus documentos e intentá nuevamente."
        )
    )
