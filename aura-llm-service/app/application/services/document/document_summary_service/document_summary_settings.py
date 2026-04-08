from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DocumentSummaryServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_SUMMARY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    pipeline_plugins: list[str] = Field(
        default_factory=lambda: [
            "validate_request",
            "retrieve_fragments",
            "generate_summary_direct",
            "map_chunks",
            "reduce_summaries",
            "fallback_summary",
        ]
    )
