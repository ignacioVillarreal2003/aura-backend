import logging
from dataclasses import dataclass
from typing import Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.processors.processor_observability import (
    log_extra,
    reformulation_total,
    reformulation_truncated_total,
    timed,
)
from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_prompts import (
    REFORMULATION_HUMAN_PROMPT,
    REFORMULATION_SYSTEM_PROMPT,
)
from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_settings import (
    QueryReformulationSettings,
)
from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_utils import (
    format_history_messages,
)
from app.application.services.generation_shared.token_estimation import tokens_to_chars
from app.application.utils.llm_json_parser import parse_json_object
from app.configuration.tracing import generation_span
from app.domain.dtos.message import Message
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_STAGE = "query_reformulation"


@dataclass(frozen=True)
class QueryReformulation:
    base_question: Optional[str] = None
    keyword_question: Optional[str] = None
    degraded: bool = False


class QueryReformulationProcessor:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            query_reformulation_settings: Optional[QueryReformulationSettings] = None,
    ) -> None:
        self._settings = query_reformulation_settings or QueryReformulationSettings()
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker

    async def run(self, state: GenerationState) -> None:
        result = await self.reformulate(
            question=state.current_message.content,
            history_messages=state.history_messages,
        )
        state.base_question = result.base_question
        state.keyword_question = result.keyword_question
        if result.degraded:
            state.reformulation_degraded = True

    async def reformulate(
            self,
            question: str,
            history_messages: list[Message],
            *,
            rewrite_query: Optional[bool] = None,
            use_keywords: Optional[bool] = None,
            history_window: Optional[int] = None,
    ) -> QueryReformulation:
        rewrite_query = self._settings.rewrite_query if rewrite_query is None else rewrite_query
        use_keywords = self._settings.use_keywords if use_keywords is None else use_keywords
        history_window = (
            self._settings.history_messages_window if history_window is None else history_window
        )
        has_history = bool(history_messages) and history_window > 0
        should_rewrite = rewrite_query and has_history

        if not should_rewrite and not use_keywords:
            return QueryReformulation()

        history_text = (
            format_history_messages(history_window, history_messages)
            if has_history
            else "(sin historial previo)"
        )

        with timed(_STAGE), generation_span(_STAGE, question):
            llm_input = [
                SystemMessage(content=REFORMULATION_SYSTEM_PROMPT),
                HumanMessage(
                    content=REFORMULATION_HUMAN_PROMPT.format(
                        history_messages=history_text,
                        question=question,
                    )
                ),
            ]

            try:
                llm = await self._build_llm()
                raw = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
            except Exception:
                reformulation_total.labels(outcome="fallback").inc()
                logger.warning(
                    "Query reformulation LLM call failed — using the original question.",
                    extra=log_extra(reason="llm_error"),
                    exc_info=True,
                )
                return QueryReformulation(degraded=True)

            try:
                result = self._parse(raw, should_rewrite=should_rewrite, use_keywords=use_keywords)
            except Exception:
                reformulation_total.labels(outcome="fallback").inc()
                logger.warning(
                    "Query reformulation produced unparseable output — using the original question.",
                    extra=log_extra(reason="json_error"),
                    exc_info=True,
                )
                return QueryReformulation(degraded=True)

            empty = result.base_question is None and result.keyword_question is None
            reformulation_total.labels(outcome="fallback" if empty else "success").inc()
            keywords_count = len(result.keyword_question.split()) if result.keyword_question else 0
            extra = log_extra(
                rewrite_applied=result.base_question is not None,
                keywords_count=keywords_count,
                base_len=len(result.base_question or ""),
                kw_len=len(result.keyword_question or ""),
            )
            if empty:
                extra["reason"] = "empty"
            logger.info("Query reformulation completed.", extra=extra)
            return result

    async def _build_llm(self) -> Runnable:
        llm = await self._ollama_llm_facade.get_llm_json()
        if self._settings.temperature is not None:
            llm = llm.bind(temperature=self._settings.temperature)
        return llm

    def _parse(self, raw: str, *, should_rewrite: bool, use_keywords: bool) -> QueryReformulation:
        data = parse_json_object(raw)

        base_question: Optional[str] = None
        if should_rewrite:
            candidate = str(data.get("base_question") or "").strip()
            if candidate:
                base_question = self._truncate_field(candidate, self._settings.max_rewrite_tokens, "base")

        keyword_question: Optional[str] = None
        if use_keywords:
            keyword_question = self._normalize_keywords(data.get("keywords"))

        return QueryReformulation(base_question=base_question, keyword_question=keyword_question)

    def _truncate_field(self, text: str, max_tokens: int, field: str) -> str:
        max_chars = tokens_to_chars(max_tokens)
        if len(text) <= max_chars:
            return text
        reformulation_truncated_total.labels(field=field).inc()
        return text[:max_chars].rstrip()

    def _normalize_keywords(self, value: Any) -> Optional[str]:
        if isinstance(value, str):
            terms = value.split()
        elif isinstance(value, (list, tuple)):
            terms = [str(item) for item in value]
        else:
            return None

        budget_chars = tokens_to_chars(self._settings.max_keywords_tokens)
        cleaned: list[str] = []
        seen: set[str] = set()
        used = 0
        truncated = False
        for term in terms:
            normalized = term.strip()
            key = normalized.lower()
            if not normalized or key in seen:
                continue
            extra = len(normalized) + (1 if cleaned else 0)
            if used + extra > budget_chars:
                truncated = True
                break
            seen.add(key)
            cleaned.append(normalized)
            used += extra

        if truncated:
            reformulation_truncated_total.labels(field="keywords").inc()
        return " ".join(cleaned) or None
