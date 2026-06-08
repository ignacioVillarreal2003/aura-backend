import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.user_interactions.agent_service.agent_state.agent_state import AgentState
from app.application.services.user_interactions.agent_service.interfaces.node_interface import NodeInterface
from app.application.services.user_interactions.agent_service.agent_settings import KeywordExtractorSettings
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

_JSON_ARRAY_PATTERN = re.compile(r"\[.*?\]", re.DOTALL)


class KeywordExtractorNode(NodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            settings: KeywordExtractorSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_lock = asyncio.Lock()
        logger.debug("KeywordExtractorNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing keyword extractor")

        resolved_query = agent_state.get("resolved_query", "") or agent_state.get("normalized_query", "")
        if not resolved_query:
            return {"keywords": []}

        try:
            await self._ensure_llm_initialized()
            keywords = await self._extract(resolved_query)
            logger.info("Keywords extracted", extra={"count": len(keywords)})
            return {"keywords": keywords}

        except Exception:
            logger.error("Keyword extraction failed — using empty keyword list", exc_info=True)
            return {"keywords": []}

    async def _extract(self, query: str) -> List[str]:
        prompt = self._build_prompt(query)
        response = await self._llm.ainvoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
        return self._parse_keywords(raw)

    def _build_prompt(self, query: str) -> List[BaseMessage]:
        return [
            SystemMessage(content=self._settings.system_prompt),
            HumanMessage(content=query),
        ]

    def _parse_keywords(self, raw: str) -> List[str]:
        match = _JSON_ARRAY_PATTERN.search(raw)
        if not match:
            logger.warning("No JSON array found in keyword extractor response", extra={"raw": raw[:200]})
            return self._fallback_keywords(raw)

        try:
            parsed = json.loads(match.group())
            keywords = [
                str(kw).strip()
                for kw in parsed
                if kw and str(kw).strip()
            ]
            return keywords[: self._settings.max_keywords]
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse keyword JSON — using fallback", extra={"raw": raw[:200]})
            return self._fallback_keywords(raw)

    @staticmethod
    def _fallback_keywords(raw: str) -> List[str]:
        tokens = re.split(r"[,\n]+", raw)
        return [t.strip().strip('"\'[]') for t in tokens if t.strip().strip('"\'[]')][:10]

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return
        async with self._llm_lock:
            if self._llm is not None:
                return
            self._llm = await self._ollama_llm_facade.get_llm_base()
            logger.debug("LLM initialized for keyword extractor")
