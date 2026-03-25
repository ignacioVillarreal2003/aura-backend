import logging
from typing import Optional
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.application.services.document_summary_service.constants.summarization_strategy import SummarizationStrategy

logger = logging.getLogger(__name__)


class DocumentSummaryServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DOCUMENT_SUMMARY_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    large_document_threshold: int = Field(default=5, ge=2, le=50)

    chunk_size: int = Field(default=5, ge=1, le=20)
    max_concurrent_chunks: int = Field(default=3, ge=1, le=10)

    max_retry_attempts: int = Field(default=3, ge=0, le=10)
    retry_delay: float = Field(default=1.0, ge=0.0, le=60.0)

    custom_system_prompt: Optional[str] = Field(default=None)

    _DEFAULT_SYSTEM_PROMPT: str = (
        "Eres un experto asistente especializado en crear resúmenes precisos y concisos "
        "basados exclusivamente en el contenido proporcionado.\n\n"
        "REGLAS ESTRICTAS:\n"
        "1. Resume SOLO usando información presente en el contenido proporcionado.\n"
        "2. NO agregues, infieras ni asumas información que no esté explícitamente en el texto.\n"
        "3. Si una sección del contenido no aporta información relevante, omítela.\n"
        "4. Prioriza los puntos clave, conceptos principales y conclusiones importantes.\n"
        "5. Mantén el resumen claro, estructurado y fácil de leer.\n"
        "6. Usa formato Markdown: encabezados (#), sub-encabezados (##), listas (-), "
        "negrita (**), tablas donde sea apropiado.\n"
        "7. Sé conciso sin perder información esencial.\n"
    )

    @model_validator(mode="after")
    def validate_coherence(self) -> "DocumentSummaryServiceSettings":
        if self.chunk_size > self.large_document_threshold:
            logger.warning(
                "chunk_size exceeds large_document_threshold — "
                "MAP_REDUCE will never produce more than one chunk",
                extra={
                    "chunk_size": self.chunk_size,
                    "large_document_threshold": self.large_document_threshold
                }
            )
        return self

    def select_strategy(self, fragment_count: int) -> SummarizationStrategy:
        if fragment_count > self.large_document_threshold:
            return SummarizationStrategy.map_reduce
        return SummarizationStrategy.direct

    @property
    def system_prompt(self) -> str:
        return self.custom_system_prompt or self._DEFAULT_SYSTEM_PROMPT
