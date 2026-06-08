import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.user_interactions.agent_service.agent_state.agent_state import AgentState
from app.application.services.user_interactions.agent_service.constants.query_intent import QueryIntent
from app.application.services.user_interactions.agent_service.agent_settings import IntentClassifierSettings
from app.application.services.user_interactions.agent_service.interfaces.node_interface import NodeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

_INTENT_PATTERN = re.compile(
    r"\b(definicion|procedimiento|normativa|busqueda_documento|comparacion|otro)\b",
    re.IGNORECASE,
)


class IntentClassifierNode(NodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            settings: IntentClassifierSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_lock = asyncio.Lock()
        logger.debug("IntentClassifierNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing intent classifier")

        resolved_query = agent_state.get("resolved_query", "") or agent_state.get("normalized_query", "")
        if not resolved_query:
            return {"intent": QueryIntent.otro.value}

        try:
            await self._ensure_llm_initialized()
            intent = await self._classify(resolved_query)
            logger.info("Intent classified", extra={"intent": intent})
            return {"intent": intent}

        except Exception:
            logger.error("Intent classification failed — defaulting to 'otro'", exc_info=True)
            return {"intent": QueryIntent.otro.value}

    async def _classify(self, query: str) -> str:
        prompt = self._build_prompt(query)
        response = await self._llm.ainvoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
        return self._parse_intent(raw)

    def _build_prompt(self, query: str) -> List[BaseMessage]:
        return [
            SystemMessage(content=self._settings.system_prompt),
            HumanMessage(content=query),
        ]

    @staticmethod
    def _parse_intent(raw: str) -> str:
        cleaned = raw.strip().lower()

        for intent in QueryIntent:
            if cleaned == intent.value:
                return intent.value

        match = _INTENT_PATTERN.search(cleaned)
        if match:
            return match.group(1).lower()

        logger.warning("Could not parse intent from LLM response — defaulting to 'otro'", extra={"raw": cleaned})
        return QueryIntent.otro.value

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return
        async with self._llm_lock:
            if self._llm is not None:
                return
            self._llm = await self._ollama_llm_facade.get_llm_base()
            logger.debug("LLM initialized for intent classifier")
