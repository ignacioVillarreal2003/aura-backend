import asyncio
import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.rag_agent_service.interfaces.rag_node_interface import RagNodeInterface
from app.application.services.rag_agent_service.rag_agent_settings import ContextEvaluatorSettings
from app.application.services.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

_SUFFICIENT_KEYWORD = "SUFICIENTE"


class ContextEvaluatorNode(RagNodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            settings: ContextEvaluatorSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_init_failed: bool = False
        self._llm_lock = asyncio.Lock()
        logger.debug("ContextEvaluatorNode initialized")

    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        logger.debug("Processing context evaluator")

        context: str = state.get("context", "")
        query: str = state.get("query", "")

        if not context:
            logger.info("No context available — marking as insufficient")
            return {"context_sufficient": False}

        if not query:
            logger.warning("No query available for evaluation — defaulting to insufficient")
            return {"context_sufficient": False}

        try:
            await self._ensure_llm_initialized()
            sufficient = await self._evaluate(query, context)
            logger.info("Context evaluated", extra={"sufficient": sufficient})
            return {"context_sufficient": sufficient}
        except Exception:
            logger.error("Context evaluation failed — defaulting to sufficient to attempt answer", exc_info=True)
            return {"context_sufficient": True}

    async def _evaluate(self, query: str, context: str) -> bool:
        prompt: List = [
            SystemMessage(content=self._settings.system_prompt),
            HumanMessage(content=f"Consulta: {query}\n\nContexto recuperado:\n{context}"),
        ]
        response = await self._llm.ainvoke(prompt)
        raw = (response.content if hasattr(response, "content") else str(response)).strip().upper()
        return _SUFFICIENT_KEYWORD in raw

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
                logger.debug("LLM initialized for context evaluator")
            except Exception as e:
                self._llm_init_failed = True
                raise RuntimeError("Failed to initialize LLM for context evaluator") from e
