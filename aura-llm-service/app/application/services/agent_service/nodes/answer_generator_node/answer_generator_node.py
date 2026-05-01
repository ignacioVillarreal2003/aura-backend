import asyncio
import logging
from typing import Any, Dict, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.agent_settings import AnswerGeneratorSettings
from app.application.services.agent_service.interfaces.node_interface import NodeInterface
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
        self._llm_init_failed: bool = False
        self._llm_lock = asyncio.Lock()
        logger.debug("AnswerGeneratorNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing answer generator")

        context = agent_state.get("context", "")
        resolved_query = agent_state.get("resolved_query", "") or agent_state.get("normalized_query", "")

        if not context:
            logger.info("No context available — returning no-information response")
            return {"answer": _NO_CONTEXT_RESPONSE, "guardrail_passed": False}

        try:
            await self._ensure_llm_initialized()
            answer = (await self._generate(resolved_query, context)).strip()

            if not answer:
                return {"answer": _NO_CONTEXT_RESPONSE, "guardrail_passed": False}

            logger.info("Answer generated", extra={"answer_length": len(answer)})
            return {"answer": answer}

        except Exception:
            logger.error("Answer generation failed", exc_info=True)
            raise RuntimeError("Failed to generate answer")

    async def _generate(self, query: str, context: str) -> str:
        response = await self._llm.ainvoke(self._build_prompt(query, context))
        return response.content if hasattr(response, "content") else str(response)

    def _build_prompt(self, query: str, context: str) -> List[BaseMessage]:
        system_content = (
            f"{self._settings.system_prompt}\n\n"
            f"Contexto documental de referencia:\n\n{context}"
        )
        return [
            SystemMessage(content=system_content),
            HumanMessage(content=query),
        ]

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return
        if self._llm_init_failed:
            raise RuntimeError("LLM initialization previously failed")
        async with self._llm_lock:
            if self._llm is not None:
                return
            if self._llm_init_failed:
                raise RuntimeError("LLM initialization previously failed")
            try:
                self._llm = await self._ollama_llm_facade.get_llm_base()
                logger.debug("LLM initialized for answer generator")
            except Exception as e:
                self._llm_init_failed = True
                raise RuntimeError("Failed to initialize LLM for answer generator") from e
