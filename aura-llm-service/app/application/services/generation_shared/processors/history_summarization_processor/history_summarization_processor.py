import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.generation_shared.generation_observability import log_extra
from app.application.services.generation_shared.processors.history_summarization_processor.history_summarization_prompts import (
    HUMAN_PROMPT,
    SYSTEM_PROMPT,
)
from app.application.services.generation_shared.processors.history_summarization_processor.history_summarization_settings import (
    HistorySummarizationSettings,
)
from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_utils import (
    format_history_messages,
)
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class HistorySummarizationProcessor:
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            history_summarization_settings: Optional[HistorySummarizationSettings] = None,
    ) -> None:
        self._settings = history_summarization_settings or HistorySummarizationSettings()
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker

    def is_needed(self, state: GenerationState, history_window: int) -> bool:
        tail = state.history_messages[-history_window:] if history_window > 0 else []
        if len(tail) < 2:
            return False
        total = sum(len(msg.content) for msg in tail)
        return total > self._settings.summarize_over_chars

    async def run(self, state: GenerationState, history_window: int) -> None:
        if not self.is_needed(state, history_window):
            return
        try:
            history_text = format_history_messages(history_window, state.history_messages)
            llm = await self._ollama_llm_facade.get_llm_base()
            if self._settings.temperature is not None:
                llm = llm.bind(temperature=self._settings.temperature)
            llm_input = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=HUMAN_PROMPT.format(history=history_text)),
            ]
            summary = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)).strip()
            if summary:
                state.history_summary = summary[: self._settings.max_summary_chars]
                logger.info(
                    "Conversation history summarized.",
                    extra=log_extra(history_messages=len(state.history_messages), summary_chars=len(state.history_summary)),
                )
        except Exception:
            logger.warning(
                "History summarization failed; falling back to deterministic trimming.",
                extra=log_extra(history_messages=len(state.history_messages)),
                exc_info=True,
            )
