from enum import StrEnum
from pydantic import BaseModel, Field

from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message
from app.domain.field_limits import (
    MAX_DESCRIPTION_CHARS,
    MAX_ITEM_TEXT_CHARS,
    MAX_QUIZ_INSTRUCTIONS_CHARS,
    MAX_QUIZ_OPTION_TEXT_CHARS,
    MAX_QUIZ_OPTIONS_PER_QUESTION,
    MAX_QUIZ_QUESTIONS,
    MAX_TITLE_CHARS,
)


class QuizQuestionType(StrEnum):
    SINGLE = "single"
    MULTIPLE = "multiple"
    BOOLEAN = "boolean"


class QuizOption(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_QUIZ_OPTION_TEXT_CHARS, description="Texto de la opción.")
    is_correct: bool = Field(default=False, description="Marca si la opción es correcta.")

    model_config = {"frozen": True}


class QuizQuestion(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_ITEM_TEXT_CHARS, description="Enunciado de la pregunta.")
    type: QuizQuestionType = Field(
        default=QuizQuestionType.SINGLE,
        description="Tipo de pregunta: single, multiple o boolean.",
    )
    explanation: str = Field(default="", max_length=MAX_QUIZ_INSTRUCTIONS_CHARS, description="Explicación de la respuesta correcta.")
    options: list[QuizOption] = Field(
        default_factory=list,
        max_length=MAX_QUIZ_OPTIONS_PER_QUESTION,
        description="Opciones de respuesta.",
    )

    model_config = {"frozen": True}


class QuizGenerateResponse(BaseModel):
    title: str = Field(..., min_length=1, max_length=MAX_TITLE_CHARS, description="Título descriptivo del cuestionario.")
    description: str = Field(default="", max_length=MAX_DESCRIPTION_CHARS, description="Breve descripción del propósito del cuestionario.")
    instructions: str = Field(default="", max_length=MAX_QUIZ_INSTRUCTIONS_CHARS, description="Instrucciones generales para el evaluado.")
    questions: list[QuizQuestion] = Field(..., min_length=1, max_length=MAX_QUIZ_QUESTIONS, description="Preguntas del cuestionario.")
    messages: list[Message] = Field(
        ...,
        description="Historial actualizado incluyendo la respuesta del asistente.",
    )
    fragments: list[FragmentResponse] = Field(
        default_factory=list,
        description="Fragmentos documentales utilizados como contexto (solo en modo rag).",
    )
    degraded_stages: list[str] = Field(
        default_factory=list,
        description=(
            "Etapas del pipeline de contexto que se degradaron (una dependencia falló y se "
            "continuó sin ella). Si no está vacío, la respuesta puede ser parcial."
        ),
    )
