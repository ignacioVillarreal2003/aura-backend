import asyncio
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.rag_agent_service.interfaces.rag_node_interface import RagNodeInterface
from app.application.services.rag_agent_service.rag_agent_settings import AnswerSynthesizerSettings
from app.application.services.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

_NO_ANSWER_RESPONSE = (
    "No se pudo generar una respuesta basada en la documentación disponible. "
    "Por favor, reformule su consulta o contacte a la unidad responsable."
)


class AnswerSynthesizerNode(RagNodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            settings: AnswerSynthesizerSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_init_failed: bool = False
        self._llm_lock = asyncio.Lock()
        logger.debug("AnswerSynthesizerNode initialized")

    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        logger.debug("Processing answer synthesizer")

        query: str = state.get("query", "")
        context: str = state.get("context", "")
        reasoning: str = state.get("reasoning", "")

        if not query or not context:
            logger.info("Missing query or context — returning fallback answer")
            return {"answer": _NO_ANSWER_RESPONSE}

        try:
            await self._ensure_llm_initialized()
            answer = await self._synthesize(query, context, reasoning)

            if not answer:
                return {"answer": _NO_ANSWER_RESPONSE}

            logger.info("Answer synthesized", extra={"answer_length": len(answer)})
            return {"answer": answer}
        except Exception:
            logger.error("Answer synthesis failed", exc_info=True)
            raise RuntimeError("Failed to synthesize answer")

    async def _synthesize(self, query: str, context: str, reasoning: str) -> str:
        reasoning_section = f"\n\nAnálisis previo:\n{reasoning}" if reasoning else ""
        user_content = (
            f"Consulta: {query}\n\n"
            f"Contexto documental:\n{context}"
            f"{reasoning_section}\n\n"
            "Sintetiza la respuesta final."
        )
        prompt: List = [
            SystemMessage(content=self._settings.system_prompt),
            HumanMessage(content=user_content),
        ]
        response = await self._llm.ainvoke(prompt)
        return (response.content if hasattr(response, "content") else str(response)).strip()

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
                logger.debug("LLM initialized for answer synthesizer")
            except Exception as e:
                self._llm_init_failed = True
                raise RuntimeError("Failed to initialize LLM for answer synthesizer") from e
