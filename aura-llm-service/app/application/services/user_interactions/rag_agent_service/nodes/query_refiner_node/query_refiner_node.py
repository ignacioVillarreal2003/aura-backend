import asyncio
import logging
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.user_interactions.rag_agent_service.interfaces.rag_node_interface import RagNodeInterface
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import QueryRefinerSettings
from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_MAX_REFINED_QUERY_CHARS = 2_000


class QueryRefinerNode(RagNodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            settings: QueryRefinerSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_lock = asyncio.Lock()
        logger.debug("QueryRefinerNode initialized")

    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        attempts = state.get("retrieval_attempts", 0) + 1
        original = state.get("query", "")

        if not original:
            return {"retrieval_attempts": attempts}

        try:
            await self._ensure_llm_initialized()
            refined = await self._refine(original, state.get("grade_reason", ""))
            refined = (refined or "").strip()[:_MAX_REFINED_QUERY_CHARS] or original
        except Exception:
            logger.error("Query refinement failed — retrying with the original query", exc_info=True)
            refined = original

        logger.info(
            "Query refined for corrective retrieval",
            extra={"attempt": attempts, "changed": refined != original},
        )
        return {"query": refined, "retrieval_attempts": attempts}

    async def _refine(self, original: str, grade_reason: str) -> str:
        user_content = f"Consulta original: {original}"
        if grade_reason:
            user_content += f"\n\nMotivo por el que la búsqueda anterior fue insuficiente: {grade_reason}"
        prompt = [
            SystemMessage(content=self._settings.system_prompt),
            HumanMessage(content=user_content),
        ]
        return await self._ollama_llm_invoker.call_llm_content(llm=self._llm, llm_input=prompt)

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return
        async with self._llm_lock:
            if self._llm is not None:
                return
            self._llm = await self._ollama_llm_facade.get_llm_base()
            logger.debug("LLM initialized for query refiner")
