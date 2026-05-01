import asyncio
import logging
from typing import Any, Dict, List, Optional
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.agent_service.agent_state.agent_state import AgentState
from app.application.services.agent_service.agent_settings import GuardrailsSettings
from app.application.services.agent_service.interfaces.node_interface import NodeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface

logger = logging.getLogger(__name__)

_CONTEXT_PREVIEW_CHARS = 600


class GuardrailsNode(NodeInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            settings: GuardrailsSettings,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._settings = settings
        self._llm: Optional[Runnable] = None
        self._llm_init_failed: bool = False
        self._llm_lock = asyncio.Lock()
        logger.debug("GuardrailsNode initialized")

    async def process(self, agent_state: AgentState) -> Dict[str, Any]:
        logger.debug("Processing guardrails")

        answer = agent_state.get("answer", "")
        context = agent_state.get("context", "")
        resolved_query = agent_state.get("resolved_query", "") or agent_state.get("normalized_query", "")

        # Step 1: rule-based check — fast, no LLM
        rule_result = self._rule_based_check(answer)

        if not rule_result["passed"]:
            logger.warning("Rule-based check failed — attempting redaction", extra={"reason": rule_result["reason"]})
            redacted = await self._try_redact(answer)
            if redacted is None:
                logger.warning("Redaction failed or not possible — rejecting")
                return {"guardrail_passed": False}
            # Re-validate the redacted answer
            if not self._rule_based_check(redacted)["passed"]:
                logger.warning("Redacted answer still fails rule check — rejecting")
                return {"guardrail_passed": False}
            logger.info("Answer redacted successfully")
            answer = redacted

        # Step 2: LLM grounding check
        try:
            await self._ensure_llm_initialized()
            passed = await self._llm_check(answer, context, resolved_query)
            logger.info("Guardrail LLM check completed", extra={"passed": passed})
            return {"answer": answer, "guardrail_passed": passed}

        except Exception:
            logger.error("LLM guardrail check failed — defaulting to approved", exc_info=True)
            return {"answer": answer, "guardrail_passed": True}

    # ── Rule-based ────────────────────────────────────────────────────────────

    def _rule_based_check(self, answer: str) -> Dict[str, Any]:
        if not answer or len(answer.strip()) < self._settings.min_answer_length:
            return {"passed": False, "reason": "answer too short or empty"}

        answer_lower = answer.lower()
        for pattern in self._settings.sensitive_patterns:
            if pattern in answer_lower:
                logger.warning("Sensitive pattern detected", extra={"pattern": pattern})
                return {"passed": False, "reason": f"sensitive pattern: {pattern}"}

        return {"passed": True, "reason": None}

    # ── Redaction ─────────────────────────────────────────────────────────────

    async def _try_redact(self, answer: str) -> Optional[str]:
        try:
            await self._ensure_llm_initialized()
            prompt = [
                SystemMessage(content=self._settings.redaction_prompt),
                HumanMessage(content=answer),
            ]
            response = await self._llm.ainvoke(prompt)
            raw = (response.content if hasattr(response, "content") else str(response)).strip()

            if "CANNOT_REDACT" in raw.upper():
                logger.warning("LLM declared answer cannot be redacted")
                return None

            return raw or None

        except Exception:
            logger.error("Redaction LLM call failed", exc_info=True)
            return None

    # ── LLM grounding check ───────────────────────────────────────────────────

    async def _llm_check(self, answer: str, context: str, query: str) -> bool:
        prompt = self._build_validation_prompt(answer, context, query)
        response = await self._llm.ainvoke(prompt)
        raw = response.content if hasattr(response, "content") else str(response)
        return self._parse_result(raw)

    def _build_validation_prompt(self, answer: str, context: str, query: str) -> List[BaseMessage]:
        context_preview = context[:_CONTEXT_PREVIEW_CHARS] + ("..." if len(context) > _CONTEXT_PREVIEW_CHARS else "")
        user_content = (
            f"Consulta original: {query}\n\n"
            f"Contexto disponible (extracto):\n{context_preview}\n\n"
            f"Respuesta a evaluar:\n{answer}"
        )
        return [
            SystemMessage(content=self._settings.system_prompt),
            HumanMessage(content=user_content),
        ]

    @staticmethod
    def _parse_result(raw: str) -> bool:
        cleaned = raw.strip().upper()
        if cleaned.startswith("APROBADO"):
            return True
        if cleaned.startswith("RECHAZADO"):
            logger.warning("LLM guardrail rejected answer", extra={"reason": raw[:200]})
            return False
        logger.warning("Unparseable guardrail result — defaulting to approved", extra={"raw": raw[:100]})
        return True

    # ── LLM init ──────────────────────────────────────────────────────────────

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
                logger.debug("LLM initialized for guardrails")
            except Exception as e:
                self._llm_init_failed = True
                raise RuntimeError("Failed to initialize LLM for guardrails") from e
