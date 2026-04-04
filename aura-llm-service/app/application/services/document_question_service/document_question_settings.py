import logging
from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class DocumentQuestionServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_QUESTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    max_context_fragments: int = Field(default=3, ge=1, le=6)

    min_question_length: int = Field(default=1, ge=1)
    max_question_length: int = Field(default=1000, ge=1, le=10_000)

    max_history_messages: int = Field(default=3, ge=0, le=20)

    custom_system_prompt: Optional[str] = Field(default=None)

    _DEFAULT_SYSTEM_PROMPT: str = (
        "Eres un asistente especializado que responde preguntas basándose exclusivamente "
        "en el contexto proporcionado.\n\n"
        "REGLAS ESTRICTAS:\n"
        "1. Responde SOLO usando la información del contexto proporcionado.\n"
        "2. Si la información no está en el contexto, indica claramente que no está disponible.\n"
        "3. NO inventes ni asumas información que no esté explícitamente presente.\n"
        "4. Usa formato Markdown: encabezados (#, ##), listas (-), negrita (**), "
        "tablas donde sea apropiado.\n"
        "5. Sé conciso pero completo.\n"
    )

    @model_validator(mode="after")
    def validate_coherence(self) -> "DocumentQuestionServiceSettings":
        if self.min_question_length > self.max_question_length:
            raise ValueError(
                f"min_question_length ({self.min_question_length}) must be "
                f"less than max_question_length ({self.max_question_length})"
            )
        return self

    @property
    def system_prompt(self) -> str:
        return self.custom_system_prompt or self._DEFAULT_SYSTEM_PROMPT
