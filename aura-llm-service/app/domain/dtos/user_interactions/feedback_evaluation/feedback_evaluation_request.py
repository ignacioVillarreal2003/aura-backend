from pydantic import BaseModel, Field
from typing import List, Optional, Any


class FeedbackEvaluationRequest(BaseModel):
    user_query: str = Field(..., description="La consulta original del usuario que generó el mensaje calificado.")
    assistant_response: str = Field(..., description="La respuesta generada por el asistente que fue calificada.")
    chat_history: List[dict] = Field(default_factory=list, description="Historial reciente de mensajes de la conversación.")
    fragments: Optional[List[dict]] = Field(default_factory=list, description="Fragmentos de contexto de RAG asociados a la respuesta.")
    feedback_reason: Optional[str] = Field(default=None, description="Motivo reportado por el usuario (e.g. incorrect, incomplete, tone).")
    feedback_comment: Optional[str] = Field(default="", description="Comentario descriptivo escrito por el usuario.")
    mode: str = Field(default="direct", description="El modo del chat (e.g. direct, rag).")

    model_config = {"frozen": True}
