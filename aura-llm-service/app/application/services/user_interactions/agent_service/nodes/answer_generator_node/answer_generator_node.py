import asyncio
import logging
from typing import Any, Dict, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.user_interactions.agent_service.agent_state.agent_state import AgentState
from app.application.services.user_interactions.agent_service.agent_settings import AnswerGeneratorSettings
from app.application.services.user_interactions.agent_service.interfaces.node_interface import NodeInterface
from app.application.services.generation_shared.prompt_augmentation import augment_system_prompt
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

_NO_CONTEXT_RESPONSE = (
    "No se encontró información suficiente en la base documental disponible para responder esta consulta. "
    "Por favor, reformule su pregunta o consulte directamente a la unidad responsable."
)


class AnswerGeneratorNode(NodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            settings: AnswerGeneratorSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_lock = asyncio.Lock()
        logger.debug("AnswerGeneratorNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing answer generator")

        context = agent_state.get("context", "")
        resolved_query = agent_state.get("resolved_query", "") or agent_state.get("normalized_query", "")

        if not context:
            logger.info("No context available — returning no-information response")
            return {"answer": _NO_CONTEXT_RESPONSE}

        try:
            await self._ensure_llm_initialized()
            answer = (
                await self._generate(
                    resolved_query,
                    context,
                    agent_state.get("operator_system_prompt"),
                    agent_state.get("response_style"),
                )
            ).strip()

            if not answer:
                return {"answer": _NO_CONTEXT_RESPONSE}

            logger.info("Answer generated", extra={"answer_length": len(answer)})
            return {"answer": answer}

        except Exception:
            logger.error("Answer generation failed — returning fallback", exc_info=True)
            return {"answer": _NO_CONTEXT_RESPONSE}

    async def _generate(
            self,
            query: str,
            context: str,
            operator_system_prompt: Optional[str] = None,
            response_style: Optional[str] = None,
    ) -> str:
        response = await self._llm.ainvoke(
            self._build_prompt(query, context, operator_system_prompt, response_style)
        )
        return response.content if hasattr(response, "content") else str(response)

    def _build_prompt(
            self,
            query: str,
            context: str,
            operator_system_prompt: Optional[str] = None,
            response_style: Optional[str] = None,
    ) -> List[BaseMessage]:
        base_system = augment_system_prompt(
            self._settings.system_prompt,
            operator_system_prompt,
            response_style,
        )
        system_content = (
            f"{base_system}\n\n"
            f"Contexto documental de referencia:\n\n{context}"
        )
        return [
            SystemMessage(content=system_content),
            HumanMessage(content=query),
        ]

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return
        async with self._llm_lock:
            if self._llm is not None:
                return
            self._llm = await self._ollama_llm_facade.get_llm_base()
            logger.debug("LLM initialized for answer generator")
