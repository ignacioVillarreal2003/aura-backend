import asyncio
import logging
from typing import Any, Dict, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.agent_settings import ContextResolverSettings
from app.application.services.agent_service.interfaces.node_interface import NodeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

_MAX_HISTORY_TURNS = 6


class ContextResolverNode(NodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            settings: ContextResolverSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_lock = asyncio.Lock()
        logger.debug("ContextResolverNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing context resolver")

        normalized_query = agent_state.get("normalized_query", "")
        messages = agent_state.get("messages", [])

        if not normalized_query:
            logger.warning("No normalized query — skipping context resolution")
            return {"resolved_query": normalized_query}

        try:
            await self._ensure_llm_initialized()
            resolved = await self._invoke_llm(normalized_query, messages)
            resolved = resolved.strip() or normalized_query

            logger.info(
                "Query resolved",
                extra={"original_length": len(normalized_query), "resolved_length": len(resolved)},
            )
            return {"resolved_query": resolved}

        except Exception:
            logger.error("Context resolver failed — falling back to normalized query", exc_info=True)
            return {"resolved_query": normalized_query}

    async def _invoke_llm(self, query: str, history: List[BaseMessage]) -> str:
        prompt = self._build_prompt(query, history)
        response = await self._llm.ainvoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _build_prompt(self, query: str, history: List[BaseMessage]) -> List[BaseMessage]:
        messages: List[BaseMessage] = [SystemMessage(content=self._settings.system_prompt)]
        recent = history[:-1][-_MAX_HISTORY_TURNS:]
        messages.extend(recent)
        messages.append(HumanMessage(content=f"Consulta a reformular: {query}"))
        return messages

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return
        async with self._llm_lock:
            if self._llm is not None:
                return
            self._llm = await self._ollama_llm_facade.get_llm_base()
            logger.debug("LLM initialized for context resolver")
