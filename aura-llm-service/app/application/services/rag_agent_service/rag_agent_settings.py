from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROMPT_MAX_CHARS = 10_000


def _validate_optional_prompt(field_name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty or whitespace-only")
    if len(value) > _PROMPT_MAX_CHARS:
        raise ValueError(f"{field_name} exceeds maximum length of {_PROMPT_MAX_CHARS} characters")
    return value


class QueryAnalyzerSettings(BaseModel):
    model_config = ConfigDict(frozen=True)
    max_keywords: int = Field(default=10, ge=1, le=30)
    custom_system_prompt: Optional[str] = None

    @field_validator("custom_system_prompt")
    @classmethod
    def _check_prompt(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_prompt("custom_system_prompt", v)

    @property
    def system_prompt(self) -> str:
        if self.custom_system_prompt is not None:
            return self.custom_system_prompt
        return (
            "Eres un analizador de consultas para un sistema de recuperación de información documental. "
            "Tu tarea es:\n"
            "1. Reformular la consulta para que sea completamente autocontenida (sin dependencia del contexto previo)\n"
            "2. Extraer palabras clave para la búsqueda\n\n"
            "Devuelve un JSON con exactamente dos campos:\n"
            "- 'query': la consulta reformulada como string\n"
            f"- 'keywords': array de hasta {self.max_keywords} términos de búsqueda relevantes\n\n"
            'Ejemplo: {"query": "¿Cuáles son los requisitos para la licencia por enfermedad?", '
            '"keywords": ["licencia enfermedad", "requisitos", "procedimiento", "normativa"]}\n\n'
            "No incluyas texto adicional fuera del JSON."
        )


class ContextEvaluatorSettings(BaseModel):
    model_config = ConfigDict(frozen=True)
    custom_system_prompt: Optional[str] = None

    @field_validator("custom_system_prompt")
    @classmethod
    def _check_prompt(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_prompt("custom_system_prompt", v)

    @property
    def system_prompt(self) -> str:
        if self.custom_system_prompt is not None:
            return self.custom_system_prompt
        return (
            "Eres un evaluador de relevancia de contexto documental. "
            "Dado una consulta y un contexto recuperado, determina si el contexto "
            "contiene información suficiente para responder la consulta.\n\n"
            "Responde ÚNICAMENTE con:\n"
            "- 'SUFICIENTE' si el contexto permite responder la consulta\n"
            "- 'INSUFICIENTE' si el contexto no contiene información relevante\n\n"
            "No incluyas explicaciones adicionales."
        )


class ReasoningSettings(BaseModel):
    model_config = ConfigDict(frozen=True)
    custom_system_prompt: Optional[str] = None

    @field_validator("custom_system_prompt")
    @classmethod
    def _check_prompt(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_prompt("custom_system_prompt", v)

    @property
    def system_prompt(self) -> str:
        if self.custom_system_prompt is not None:
            return self.custom_system_prompt
        return (
            "Eres un asistente experto en análisis documental institucional. "
            "Tu tarea es razonar paso a paso sobre cómo responder una consulta basándote "
            "EXCLUSIVAMENTE en el contexto documental proporcionado.\n\n"
            "Instrucciones:\n"
            "1. Identifica qué información del contexto es relevante para la consulta\n"
            "2. Analiza las relaciones entre los fragmentos relevantes\n"
            "3. Determina qué partes de la respuesta pueden sustentarse en el contexto\n"
            "4. Identifica posibles lagunas de información\n\n"
            "Expresa tu razonamiento de forma estructurada y concisa. "
            "No generes la respuesta final, solo el análisis."
        )


class AnswerSynthesizerSettings(BaseModel):
    model_config = ConfigDict(frozen=True)
    custom_system_prompt: Optional[str] = None

    @field_validator("custom_system_prompt")
    @classmethod
    def _check_prompt(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_prompt("custom_system_prompt", v)

    @property
    def system_prompt(self) -> str:
        if self.custom_system_prompt is not None:
            return self.custom_system_prompt
        return (
            "Eres un asistente especializado en documentación institucional, normativa legal y procedimientos "
            "administrativos. Tu función es sintetizar una respuesta clara y precisa basándote EXCLUSIVAMENTE "
            "en el contexto documental y el análisis previo proporcionados.\n\n"
            "Instrucciones obligatorias:\n"
            "1. Responde únicamente con información presente en el contexto\n"
            "2. Cita las fuentes usando el formato [Documento #ID] al final de cada afirmación relevante\n"
            "3. Mantén un lenguaje técnico, formal y preciso\n"
            "4. Si el contexto contiene información parcial o contradictoria, señálalo claramente\n"
            "5. No inventes ni extrapoles información que no esté en el contexto"
        )


class RagAgentServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RAG_AGENT_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_fragments: int = Field(default=12, ge=1, le=50)
    max_context_chars: int = Field(default=10_000, ge=1_000, le=50_000)

    query_analyzer: QueryAnalyzerSettings = Field(default_factory=QueryAnalyzerSettings)
    context_evaluator: ContextEvaluatorSettings = Field(default_factory=ContextEvaluatorSettings)
    reasoning: ReasoningSettings = Field(default_factory=ReasoningSettings)
    answer_synthesizer: AnswerSynthesizerSettings = Field(default_factory=AnswerSynthesizerSettings)
