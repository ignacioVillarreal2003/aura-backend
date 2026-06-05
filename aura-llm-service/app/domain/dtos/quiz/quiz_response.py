from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field

from app.domain.dtos.fragment.fragment_response import FragmentResponse
from app.domain.dtos.message import Message


class QuizQuestionType(StrEnum):
    SINGLE = "single"
    MULTIPLE = "multiple"
    BOOLEAN = "boolean"
    OPEN = "open"


class QuizOption(BaseModel):
    text: str = Field(..., description="Texto de la opción.")
    is_correct: bool = Field(default=False, description="Marca si la opción es correcta.")

    model_config = {"frozen": True}


class QuizQuestion(BaseModel):
    question: str = Field(..., description="Enunciado de la pregunta.")
    type: QuizQuestionType = Field(
        default=QuizQuestionType.SINGLE,
        description="Tipo de pregunta: single, multiple, boolean u open.",
    )
    explanation: str = Field(default="", description="Explicación de la respuesta correcta.")
    options: list[QuizOption] = Field(
        default_factory=list,
        description="Opciones de respuesta (vacío para preguntas de tipo 'open').",
    )

    model_config = {"frozen": True}


class QuizGenerateResponse(BaseModel):
    title: str = Field(..., description="Título descriptivo del cuestionario.")
    instructions: str = Field(default="", description="Instrucciones generales para el evaluado.")
    passing_score: Optional[int] = Field(
        default=None,
        ge=0,
        le=100,
        description="Puntaje mínimo (0-100) para aprobar. Null si no aplica.",
    )
    questions: list[QuizQuestion] = Field(..., description="Preguntas del cuestionario.")
    messages: list[Message] = Field(
        ...,
        description="Historial actualizado incluyendo la respuesta del asistente.",
    )
    fragments: list[FragmentResponse] = Field(
        default_factory=list,
        description="Fragmentos documentales utilizados como contexto (solo en modo rag).",
    )
