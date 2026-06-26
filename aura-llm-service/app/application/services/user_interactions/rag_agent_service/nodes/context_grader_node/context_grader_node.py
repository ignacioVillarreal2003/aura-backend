import asyncio
import json
import logging
import re
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.user_interactions.rag_agent_service.interfaces.rag_node_interface import RagNodeInterface
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import ContextGraderSettings
from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_CONTEXT_PREVIEW_CHARS = 6_000


class ContextGraderNode(RagNodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            settings: ContextGraderSettings,
            max_retrieval_attempts: int,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._settings = settings
        self._max_retrieval_attempts = max_retrieval_attempts
        self._llm: Optional[Runnable] = None
        self._llm_lock = asyncio.Lock()
        logger.debug("ContextGraderNode initialized")

    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        query: str = state.get("query", "")
        context: str = state.get("context", "")
        graph_facts: str = state.get("graph_facts", "")
        attempts: int = state.get("retrieval_attempts", 0)

        if not query or (not context and not graph_facts):
            can_retry = attempts < self._max_retrieval_attempts
            logger.info("Context grader: nothing to grade", extra={"can_retry": can_retry})
            return {"context_sufficient": False, "grade_reason": "empty context", "can_retry": can_retry}

        try:
            await self._ensure_llm_initialized()
            sufficient, reason = await self._grade(query, context, graph_facts)
        except Exception:
            logger.error("Context grader failed — treating context as sufficient (fail-open)", exc_info=True)
            return {"context_sufficient": True, "grade_reason": "grader error (fail-open)", "can_retry": False}

        can_retry = (not sufficient) and (attempts < self._max_retrieval_attempts)
        logger.info(
            "Context graded",
            extra={"sufficient": sufficient, "attempts": attempts, "can_retry": can_retry},
        )
        return {"context_sufficient": sufficient, "grade_reason": reason, "can_retry": can_retry}

    async def _grade(self, query: str, context: str, graph_facts: str) -> tuple[bool, str]:
        sections = [f"Consulta: {query}"]
        if context:
            sections.append(f"Contexto documental (extracto):\n{context[:_CONTEXT_PREVIEW_CHARS]}")
        if graph_facts:
            sections.append(f"Hechos del grafo (extracto):\n{graph_facts[:_CONTEXT_PREVIEW_CHARS]}")
        prompt = [
            SystemMessage(content=self._settings.system_prompt),
            HumanMessage(content="\n\n".join(sections)),
        ]
        raw = await self._ollama_llm_invoker.call_llm_content(llm=self._llm, llm_input=prompt)
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> tuple[bool, str]:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return True, "unparseable grader output (fail-open)"
        data = json.loads(match.group())
        sufficient = bool(data.get("sufficient", True))
        reason = str(data.get("reason", "") or "").strip()[:200]
        return sufficient, reason

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return
        async with self._llm_lock:
            if self._llm is not None:
                return
            self._llm = await self._ollama_llm_facade.get_llm_json()
            logger.debug("LLM initialized for context grader")
