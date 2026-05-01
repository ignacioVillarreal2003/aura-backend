from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROMPT_MAX_CHARS = 10_000

_DEFAULT_SENSITIVE_PATTERNS: tuple[str, ...] = (
    "clasificado",
    "confidencial",
    "secreto",
    "reservado",
    "uso interno",
    "no divulgar",
    "restringido",
)

_VALID_INTENTS_LINE = (
    "definicion, procedimiento, normativa, busqueda_documento, comparacion, otro"
)


def _validate_optional_prompt(field_name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if not value.strip():
        raise ValueError(f"{field_name} cannot be empty or whitespace-only")
    if len(value) > _PROMPT_MAX_CHARS:
        raise ValueError(f"{field_name} exceeds maximum length of {_PROMPT_MAX_CHARS} characters")
    return value


class ContextResolverSettings(BaseModel):
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
            "Eres un experto en reformular consultas para sistemas de búsqueda documental institucional. "
            "Tu tarea es reescribir la última pregunta del usuario para que sea completamente autocontenida, "
            "eliminando toda ambigüedad y sin depender del contexto previo de la conversación.\n\n"
            "Reglas:\n"
            "- Incorpora toda la información de contexto necesaria del historial de conversación\n"
            "- Reemplaza referencias ambiguas (eso, aquello, el mencionado, la misma, etc.) "
            "con los términos específicos a los que se refieren\n"
            "- Mantén el significado y la intención original de la consulta\n"
            "- Devuelve ÚNICAMENTE la consulta reescrita, sin explicaciones ni prefijos\n"
            "- Si la consulta ya es completamente autocontenida, devuélvela sin cambios"
        )


class IntentClassifierSettings(BaseModel):
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
            "Eres un clasificador de consultas para un sistema documental institucional y normativo. "
            "Clasifica la siguiente consulta en UNA de estas categorías:\n\n"
            f"- {_VALID_INTENTS_LINE}\n\n"
            "Definiciones:\n"
            "- definicion: pregunta por el significado o concepto de algo\n"
            "- procedimiento: pregunta por pasos, procesos o cómo hacer algo\n"
            "- normativa: pregunta por leyes, reglamentos, decretos o regulaciones\n"
            "- busqueda_documento: busca un documento específico por nombre, número o fecha\n"
            "- comparacion: compara dos o más elementos, leyes o procedimientos\n"
            "- otro: consulta que no encaja en las categorías anteriores\n\n"
            "Responde con ÚNICAMENTE la palabra de la categoría, sin explicaciones ni puntuación."
        )


class EntityExtractorSettings(BaseModel):
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
            "Eres un extractor de entidades nombradas para un sistema documental institucional. "
            "A partir de la consulta, extrae entidades jurídico-institucionales organizadas por tipo.\n\n"
            "Tipos de entidades a extraer:\n"
            "- leyes: leyes, decretos, resoluciones, ordenanzas, circulares (con número y año si se mencionan)\n"
            "- organismos: ministerios, secretarías, subsecretarías, organismos, entes, agencias\n"
            "- cargos: puestos, roles, cargos jerárquicos (director, secretario, ministro, etc.)\n"
            "- fechas: años, períodos, vigencias, plazos mencionados\n\n"
            "Devuelve ÚNICAMENTE un objeto JSON con estas cuatro claves. "
            "Si no hay entidades de un tipo, devuelve una lista vacía para esa clave.\n\n"
            'Ejemplo: {"leyes": ["Ley 26.206", "Decreto 160/2023"], '
            '"organismos": ["Ministerio de Educación"], '
            '"cargos": ["Director Nacional"], "fechas": ["2023"]}\n\n'
            "No incluyas explicaciones ni texto fuera del JSON."
        )


def _keyword_default_system_prompt(max_keywords: int) -> str:
    return (
        "Eres un experto en extracción de palabras clave y entidades para sistemas de búsqueda "
        "documental institucional y normativo.\n\n"
        "A partir de la consulta proporcionada, extrae términos de búsqueda relevantes incluyendo:\n"
        "- Leyes, decretos, resoluciones y normativas (con su número si se menciona)\n"
        "- Organismos, ministerios, secretarías y unidades administrativas\n"
        "- Cargos, roles y posiciones institucionales\n"
        "- Procedimientos, procesos y trámites específicos\n"
        "- Fechas, períodos y vigencias relevantes\n"
        "- Conceptos técnicos y jurídicos clave\n\n"
        f"Devuelve ÚNICAMENTE un array JSON con hasta {max_keywords} strings, "
        "ordenados de mayor a menor relevancia.\n"
        'Ejemplo: ["ley educación superior", "ministerio educación", "acreditación", "2023"]\n'
        "No incluyas explicaciones ni texto adicional fuera del JSON."
    )


class KeywordExtractorSettings(BaseModel):
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
        return _keyword_default_system_prompt(self.max_keywords)


class AnswerGeneratorSettings(BaseModel):
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
            "administrativos. Tu función es responder consultas basándote EXCLUSIVAMENTE en el contexto "
            "documental proporcionado.\n\n"
            "Instrucciones obligatorias:\n"
            "1. Responde únicamente con información presente en el contexto proporcionado\n"
            "2. Cita las fuentes usando el formato [Documento #ID] al final de cada afirmación relevante\n"
            "3. Si la información solicitada no está en el contexto, indícalo explícitamente: "
            "'No se encontró información sobre este tema en la base documental disponible'\n"
            "4. Mantén un lenguaje técnico, formal y preciso apropiado para documentación institucional\n"
            "5. No inventes, extrapoles ni asumas información que no esté explícitamente en el contexto\n"
            "6. Si el contexto contiene información parcial o contradictoria, señálalo claramente"
        )


class GuardrailsSettings(BaseModel):
    model_config = ConfigDict(frozen=True)
    custom_system_prompt: Optional[str] = None
    custom_redaction_prompt: Optional[str] = None
    min_answer_length: int = Field(default=10, ge=1)
    sensitive_patterns: tuple[str, ...] = Field(default=_DEFAULT_SENSITIVE_PATTERNS)

    @field_validator("custom_system_prompt")
    @classmethod
    def _check_system_prompt(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_prompt("custom_system_prompt", v)

    @field_validator("custom_redaction_prompt")
    @classmethod
    def _check_redaction_prompt(cls, v: Optional[str]) -> Optional[str]:
        return _validate_optional_prompt("custom_redaction_prompt", v)

    @property
    def system_prompt(self) -> str:
        if self.custom_system_prompt is not None:
            return self.custom_system_prompt
        return (
            "Eres un validador de seguridad de contenido para un sistema documental institucional. "
            "Tu tarea es verificar que una respuesta generada por IA sea apropiada.\n\n"
            "Evalúa si la respuesta:\n"
            "1. Está fundamentada en el contexto proporcionado (no inventa información)\n"
            "2. No revela información clasificada o sensible de forma inapropiada\n"
            "3. Es coherente con la consulta original\n"
            "4. Es profesional y apropiada para un sistema institucional\n\n"
            "Responde ÚNICAMENTE con:\n"
            "- 'APROBADO' si la respuesta es apropiada\n"
            "- 'RECHAZADO: {motivo breve}' si hay problemas\n\n"
            "No incluyas explicaciones adicionales."
        )

    @property
    def redaction_prompt(self) -> str:
        if self.custom_redaction_prompt is not None:
            return self.custom_redaction_prompt
        return (
            "Eres un redactor de contenido sensible para un sistema documental institucional. "
            "La siguiente respuesta contiene información que debe ser eliminada o reemplazada "
            "antes de ser entregada al usuario.\n\n"
            "Instrucciones:\n"
            "1. Elimina o reemplaza con '[REDACTADO]' cualquier referencia a información "
            "clasificada, confidencial, secreta o de uso interno\n"
            "2. Conserva el resto de la respuesta con el mismo formato y estructura\n"
            "3. Si la respuesta completa es inapropiada y no puede redactarse, responde exactamente: CANNOT_REDACT\n\n"
            "Devuelve directamente la respuesta redactada o CANNOT_REDACT. "
            "No incluyas explicaciones ni prefijos."
        )


class AgentServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    max_vector_fragments: int = Field(default=10, ge=1, le=50)
    max_keyword_fragments: int = Field(default=10, ge=1, le=50)
    max_rerank_fragments: int = Field(default=8, ge=1, le=50)
    max_context_chars: int = Field(default=8_000, ge=1_000, le=50_000)

    context_resolver: ContextResolverSettings = Field(default_factory=ContextResolverSettings)
    intent_classifier: IntentClassifierSettings = Field(default_factory=IntentClassifierSettings)
    entity_extractor: EntityExtractorSettings = Field(default_factory=EntityExtractorSettings)
    keyword_extractor: KeywordExtractorSettings = Field(default_factory=KeywordExtractorSettings)
    answer_generator: AnswerGeneratorSettings = Field(default_factory=AnswerGeneratorSettings)
    guardrails: GuardrailsSettings = Field(default_factory=GuardrailsSettings)

    @model_validator(mode="after")
    def validate_coherence(self) -> "AgentServiceSettings":
        total = self.max_vector_fragments + self.max_keyword_fragments
        if self.max_rerank_fragments > total:
            raise ValueError(
                f"max_rerank_fragments ({self.max_rerank_fragments}) cannot exceed "
                f"max_vector_fragments + max_keyword_fragments ({total})"
            )
        return self
