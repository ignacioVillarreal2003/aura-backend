import logging
from typing import Any, Dict

from app.application.services.user_interactions.rag_agent_service.interfaces.rag_node_interface import RagNodeInterface
from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState

logger = logging.getLogger(__name__)

_FALLBACK_ANSWER = (
    "No se encontró información suficiente en la base documental disponible para responder esta consulta. "
    "Por favor, reformule su pregunta o consulte directamente a la unidad responsable."
)


class FallbackNode(RagNodeInterface):
    def __init__(self) -> None:
        logger.debug("FallbackNode initialized")

    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        logger.info("Fallback triggered — no sufficient context found")
        return {"answer": _FALLBACK_ANSWER, "fallback_triggered": True}
