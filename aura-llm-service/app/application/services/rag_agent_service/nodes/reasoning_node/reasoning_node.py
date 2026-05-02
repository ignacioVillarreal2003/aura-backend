import asyncio
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.rag_agent_service.interfaces.rag_node_interface import RagNodeInterface
from app.application.services.rag_agent_service.rag_agent_settings import ReasoningSettings
from app.application.services.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)


class ReasoningNode(RagNodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            settings: ReasoningSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_init_failed: bool = False
        self._llm_lock = asyncio.Lock()
        logger.debug("ReasoningNode initialized")

    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        logger.debug("Processing reasoning")

        query: str = state.get("query", "")
        context: str = state.get("context", "")

        if not query or not context:
            logger.warning("Missing query or context for reasoning — skipping")
            return {"reasoning": ""}

        try:
            await self._ensure_llm_initialized()
            reasoning = await self._reason(query, context)
            logger.info("Reasoning completed", extra={"reasoning_length": len(reasoning)})
            return {"reasoning": reasoning}
        except Exception:
            logger.error("Reasoning failed — continuing without it", exc_info=True)
            return {"reasoning": ""}

    async def _reason(self, query: str, context: str) -> str:
        prompt: List = [
            SystemMessage(content=self._settings.system_prompt),
            HumanMessage(content=f"Consulta: {query}\n\nContexto documental:\n{context}"),
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
                logger.debug("LLM initialized for reasoning")
            except Exception as e:
                self._llm_init_failed = True
                raise RuntimeError("Failed to initialize LLM for reasoning") from e
