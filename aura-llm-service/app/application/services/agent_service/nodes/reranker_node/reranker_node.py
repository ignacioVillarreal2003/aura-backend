import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.agent_service.agent_settings import AgentServiceSettings
from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.interfaces.node_interface import NodeInterface
from app.infrastructure.http.document_context_provider.dtos.fragment_response import FragmentResponse
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

_MAX_RERANKER_INPUT = 15
_FRAGMENT_PREVIEW_CHARS = 400
_JSON_ARRAY_PATTERN = re.compile(r"\[[\s\d,]+\]")

_SYSTEM_PROMPT = (
    "Eres un experto en relevancia documental para sistemas institucionales. "
    "Dado una consulta y una lista de fragmentos de documentos, tu tarea es determinar "
    "el orden de relevancia de los fragmentos.\n\n"
    "Responde ÚNICAMENTE con un array JSON de índices (base 0) ordenados de mayor a menor relevancia.\n"
    "Ejemplo para 4 fragmentos: [2, 0, 3, 1]\n"
    "Incluye TODOS los índices en el array."
)


class RerankerNode(NodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            settings: AgentServiceSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_init_failed: bool = False
        self._llm_lock = asyncio.Lock()
        logger.debug("RerankerNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing reranker")

        fragments: List[FragmentResponse] = agent_state.get("retrieved_fragments", [])
        resolved_query = agent_state.get("resolved_query", "") or agent_state.get("normalized_query", "")

        if not fragments:
            return {"reranked_fragments": []}

        if len(fragments) == 1:
            return {"reranked_fragments": fragments}

        candidates = fragments[:_MAX_RERANKER_INPUT]

        try:
            await self._ensure_llm_initialized()
            reranked = await self._rerank(resolved_query, candidates)
            final = reranked[: self._settings.max_rerank_fragments]
            logger.info("Reranking completed", extra={"input": len(candidates), "output": len(final)})
            return {"reranked_fragments": final}

        except Exception:
            logger.error("Reranking failed — using original retrieval order", exc_info=True)
            return {"reranked_fragments": fragments[: self._settings.max_rerank_fragments]}

    async def _rerank(self, query: str, fragments: List[FragmentResponse]) -> List[FragmentResponse]:
        prompt = self._build_prompt(query, fragments)
        response = await self._llm.ainvoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
        ordering = self._parse_ordering(raw, len(fragments))
        return [fragments[i] for i in ordering if 0 <= i < len(fragments)]

    @staticmethod
    def _build_prompt(query: str, fragments: List[FragmentResponse]) -> List[BaseMessage]:
        fragments_text = "\n\n".join(
            f"Fragmento [{i}] (Documento #{f.document_id}):\n{f.content[:_FRAGMENT_PREVIEW_CHARS]}"
            for i, f in enumerate(fragments)
        )
        user_content = f"Consulta: {query}\n\n{fragments_text}"
        return [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

    @staticmethod
    def _parse_ordering(raw: str, n: int) -> List[int]:
        match = _JSON_ARRAY_PATTERN.search(raw)
        if not match:
            logger.warning("No valid ordering array found in reranker response")
            return list(range(n))

        try:
            ordering = json.loads(match.group())
            seen: set = set()
            valid = []
            for idx in ordering:
                if isinstance(idx, int) and 0 <= idx < n and idx not in seen:
                    valid.append(idx)
                    seen.add(idx)
            # Append any missing indices at the end
            for idx in range(n):
                if idx not in seen:
                    valid.append(idx)
            return valid
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse reranker ordering JSON — using original order")
            return list(range(n))

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
                logger.debug("LLM initialized for reranker")
            except Exception as e:
                self._llm_init_failed = True
                raise RuntimeError("Failed to initialize LLM for reranker") from e
