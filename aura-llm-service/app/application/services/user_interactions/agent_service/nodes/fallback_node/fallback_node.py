import logging
from typing import Any, Dict

from app.application.services.user_interactions.agent_service.agent_state.agent_state import AgentState
from app.application.services.user_interactions.agent_service.interfaces.node_interface import NodeInterface

logger = logging.getLogger(__name__)

_NO_CONTEXT_ANSWER = (
    "No se encontró información suficiente en la base documental disponible para responder esta consulta. "
    "Por favor, reformule su pregunta o consulte directamente a la unidad responsable."
)
_GUARDRAIL_REJECTED_ANSWER = (
    "La consulta no pudo ser procesada en este momento. "
    "Por favor, reformule su pregunta o consulte directamente a la unidad responsable."
)


class FallbackNode(NodeInterface):
    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.info("Fallback node triggered")

        has_context = bool(agent_state.get("context", "").strip())
        guardrail_passed = agent_state.get("guardrail_passed", True)

        if has_context and not guardrail_passed:
            answer = _GUARDRAIL_REJECTED_ANSWER
        else:
            answer = _NO_CONTEXT_ANSWER

        return {
            "answer": answer,
            "guardrail_passed": True,
            "fallback_triggered": True,
        }
