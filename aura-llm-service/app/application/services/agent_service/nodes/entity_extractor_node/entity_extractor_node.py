import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.interfaces.node_interface import NodeInterface
from app.application.services.agent_service.agent_settings import EntityExtractorSettings
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

_ENTITY_KEYS = ("leyes", "organismos", "cargos", "fechas")
_JSON_OBJECT_PATTERN = re.compile(r"\{.*?\}", re.DOTALL)
_EMPTY_ENTITIES: dict = {k: [] for k in _ENTITY_KEYS}


class EntityExtractorNode(NodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            settings: EntityExtractorSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_init_failed: bool = False
        self._llm_lock = asyncio.Lock()
        logger.debug("EntityExtractorNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing entity extractor")

        resolved_query = agent_state.get("resolved_query", "") or agent_state.get("normalized_query", "")
        if not resolved_query:
            return {"entities": _EMPTY_ENTITIES}

        try:
            await self._ensure_llm_initialized()
            entities = await self._extract(resolved_query)
            total = sum(len(v) for v in entities.values())
            logger.info("Entities extracted", extra={"total": total, "types": {k: len(v) for k, v in entities.items()}})
            return {"entities": entities}

        except Exception:
            logger.error("Entity extraction failed — returning empty entities", exc_info=True)
            return {"entities": _EMPTY_ENTITIES}

    async def _extract(self, query: str) -> dict:
        prompt = self._build_prompt(query)
        response = await self._llm.ainvoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
        return self._parse_entities(raw)

    def _build_prompt(self, query: str) -> List[BaseMessage]:
        return [
            SystemMessage(content=self._settings.system_prompt),
            HumanMessage(content=query),
        ]

    @staticmethod
    def _parse_entities(raw: str) -> dict:
        match = _JSON_OBJECT_PATTERN.search(raw)
        if not match:
            logger.warning("No JSON object found in entity extractor response", extra={"raw": raw[:200]})
            return _EMPTY_ENTITIES

        try:
            parsed = json.loads(match.group())
            return {
                key: [str(v).strip() for v in parsed.get(key, []) if str(v).strip()]
                for key in _ENTITY_KEYS
            }
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse entity JSON", extra={"raw": raw[:200]})
            return _EMPTY_ENTITIES

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
                logger.debug("LLM initialized for entity extractor")
            except Exception as e:
                self._llm_init_failed = True
                raise RuntimeError("Failed to initialize LLM for entity extractor") from e
