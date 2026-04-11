from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentQuestionServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_QUESTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    pipeline_plugins: list[str] = Field(
        default_factory=lambda: [
            "validate_request",
            "rewrite_query",
            "retrieve_context",
            "generate_answer",
            "fallback_answer",
        ]
    )
