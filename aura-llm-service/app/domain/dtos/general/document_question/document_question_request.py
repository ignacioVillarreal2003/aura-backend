from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.dtos.message import Message


class DocumentQuestionRequestSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_QUESTION_REQUEST_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    min_question_length: int = Field(default=1, ge=1)
    max_question_length: int = Field(default=1000, ge=1, le=10_000)
    max_history_messages: int = Field(default=10, ge=0, le=100)

    @model_validator(mode="after")
    def validate_question_length_range(self) -> "DocumentQuestionRequestSettings":
        if self.min_question_length > self.max_question_length:
            raise ValueError(
                f"min_question_length ({self.min_question_length}) must be "
                f"less than or equal to max_question_length ({self.max_question_length})"
            )
        return self


_settings = DocumentQuestionRequestSettings()


class DocumentQuestionRequest(BaseModel):
    messages: list[Message] = Field(...)

    @model_validator(mode="after")
    def validate_request_logic(self) -> "DocumentQuestionRequest":
        if not self.messages:
            raise ValueError("Debe enviar al menos un mensaje con la consulta actual.")

        question = self.messages[-1].content
        if not question or not question.strip():
            raise ValueError("La pregunta no puede estar vacía.")

        question_length = len(question.strip())
        if question_length < _settings.min_question_length:
            raise ValueError(
                f"La pregunta es demasiado corta. Debe tener al menos "
                f"{_settings.min_question_length} caracteres."
            )

        if question_length > _settings.max_question_length:
            raise ValueError(
                f"La pregunta es demasiado larga. No debe exceder "
                f"{_settings.max_question_length} caracteres."
            )

        history_count = len(self.messages) - 1
        if history_count > _settings.max_history_messages:
            raise ValueError(
                f"El historial de mensajes es demasiado largo. "
                f"Máximo permitido: {_settings.max_history_messages} mensajes."
            )

        return self
