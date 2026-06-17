import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.user_interactions.rag_agent_service.constants.rag_query_intent import RagQueryIntent
from app.application.services.user_interactions.rag_agent_service.interfaces.rag_node_interface import RagNodeInterface
from app.application.services.user_interactions.rag_agent_service.rag_agent_settings import QueryAnalyzerSettings
from app.application.services.user_interactions.rag_agent_service.rag_agent_state.rag_agent_state import RagAgentState
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_MAX_HISTORY_MESSAGES = 6


class QueryAnalyzerNode(RagNodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            settings: QueryAnalyzerSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_lock = asyncio.Lock()
        logger.debug("QueryAnalyzerNode initialized")

    async def process(self, state: RagAgentState) -> Dict[str, Any]:
        logger.debug("Processing query analyzer")

        messages: List[AnyMessage] = state.get("messages", [])

        last_human = self._get_last_human_message(messages)
        if not last_human:
            logger.warning("No human message found in state")
            return {"query": "", "keywords": [], "intent": RagQueryIntent.question.value}

        history = self._get_recent_history(messages)

        try:
            await self._ensure_llm_initialized()
            result = await self._analyze(last_human, history)
            logger.info(
                "Query analyzed",
                extra={
                    "query_length": len(result["query"]),
                    "keywords_count": len(result["keywords"]),
                    "intent": result["intent"],
                },
            )
            return result
        except Exception:
            logger.error("Query analysis failed — using raw message as fallback", exc_info=True)
            return {"query": last_human, "keywords": [], "intent": RagQueryIntent.question.value}

    async def _analyze(self, query: str, history: List[AnyMessage]) -> Dict[str, Any]:
        history_text = self._format_history(history)
        user_content = (
            f"Historial de conversación:\n{history_text}\n\n" if history_text else ""
        ) + f"Consulta actual: {query}"

        raw = await self._ollama_llm_invoker.call_llm_content(
            llm=self._llm,
            llm_input=[
                SystemMessage(content=self._settings.system_prompt),
                HumanMessage(content=user_content),
            ],
        )
        return self._parse_response(raw, query)

    def _parse_response(self, raw: str, fallback_query: str) -> Dict[str, Any]:
        try:
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")

            data = json.loads(json_match.group())
            query = str(data.get("query", fallback_query)).strip() or fallback_query
            keywords_raw = data.get("keywords", [])
            keywords = [str(k).strip() for k in keywords_raw if k and str(k).strip()]
            intent_raw = str(data.get("intent", "")).strip().lower()
            intent = (
                intent_raw
                if intent_raw in {i.value for i in RagQueryIntent}
                else RagQueryIntent.question.value
            )
            return {
                "query": query,
                "keywords": keywords[: self._settings.max_keywords],
                "intent": intent,
            }
        except Exception:
            logger.warning("Failed to parse query analyzer response — using fallback", exc_info=True)
            return {"query": fallback_query, "keywords": [], "intent": RagQueryIntent.question.value}

    async def _ensure_llm_initialized(self) -> None:
        if self._llm is not None:
            return
        async with self._llm_lock:
            if self._llm is not None:
                return
            self._llm = await self._ollama_llm_facade.get_llm_base()
            logger.debug("LLM initialized for query analyzer")

    @staticmethod
    def _get_last_human_message(messages: List[AnyMessage]) -> Optional[str]:
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return str(message.content)
        return None

    @staticmethod
    def _get_recent_history(messages: List[AnyMessage]) -> List[AnyMessage]:
        if len(messages) <= 1:
            return []
        return messages[-(min(len(messages), _MAX_HISTORY_MESSAGES + 1)):-1]

    @staticmethod
    def _format_history(messages: List[AnyMessage]) -> str:
        if not messages:
            return ""
        lines = []
        for msg in messages:
            role = "Usuario" if isinstance(msg, HumanMessage) else "Asistente"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)
