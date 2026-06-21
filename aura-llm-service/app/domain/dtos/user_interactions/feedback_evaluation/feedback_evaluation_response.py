from pydantic import BaseModel, Field


class FeedbackEvaluationResponse(BaseModel):
    failure_category: str = Field(..., description="Categoría de falla detectada (e.g. retrieval_miss, hallucination, reasoning, style, incomplete, other, no_failure).")
    failure_explanation: str = Field(..., description="Explicación detallada de dónde y por qué falló el modelo.")
    expected_output: str = Field(..., description="La respuesta óptima corregida que el asistente debió dar.")
    confidence_score: float = Field(..., description="Puntaje de confianza del análisis del juez [0.0 - 1.0].")
    judge_model: str = Field(..., description="El nombre del modelo juez utilizado para realizar la evaluación.")

    model_config = {
        "from_attributes": True
    }
