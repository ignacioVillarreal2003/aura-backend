from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentActionServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_ACTION_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    pipeline_plugins: list[str] = Field(
        default_factory=lambda: [
            "validate_request",
            "retrieve_fragments",
            "generate_response_direct",
            "map_chunks",
            "reduce_results",
            "fallback_response",
        ]
    )
