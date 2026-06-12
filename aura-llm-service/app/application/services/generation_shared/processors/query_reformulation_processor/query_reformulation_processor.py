import logging
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_prompts import (
    BASE_QUESTION_HUMAN_PROMPT,
    BASE_QUESTION_SYSTEM_PROMPT,
    KEYWORD_QUESTION_HUMAN_PROMPT,
    KEYWORD_QUESTION_SYSTEM_PROMPT,
)
from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_settings import (
    QueryReformulationSettings,
)
from app.application.services.generation_shared.processors.query_reformulation_processor.query_reformulation_utils import (
    format_history_messages,
)
from app.domain.dtos.message import Message
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


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
        if state.history_messages:
            state.base_question = await self._build_base_question(
                question=state.current_message.content,
                history_messages=state.history_messages,
            )

        if self._settings.use_keywords:
            state.keyword_question = await self._build_keywords_question(
                question=state.current_message.content,
                base_question=state.base_question,
            )

    async def _build_base_question(
            self,
            question: str,
            history_messages: list[Message],
    ) -> Optional[str]:
        llm = await self._ollama_llm_facade.get_llm_base()
        formatted_history = format_history_messages(self._settings.history_messages_window, history_messages)
        llm_input = [
            SystemMessage(content=BASE_QUESTION_SYSTEM_PROMPT),
            HumanMessage(
                content=BASE_QUESTION_HUMAN_PROMPT.format(
                    history_messages=formatted_history,
                    question=question,
                )
            ),
        ]
        try:
            result = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)).strip()
            if not result:
                raise ValueError("Empty response from LLM.")
            return result
        except Exception:
            logger.warning("Failed to build contextual query — falling back to original.", exc_info=True)
            return None

    async def _build_keywords_question(
            self,
            question: str,
            base_question: Optional[str],
    ) -> Optional[str]:
        llm = await self._ollama_llm_facade.get_llm_base()
        effective_question = base_question or question
        llm_input = [
            SystemMessage(content=KEYWORD_QUESTION_SYSTEM_PROMPT),
            HumanMessage(content=KEYWORD_QUESTION_HUMAN_PROMPT.format(question=effective_question)),
        ]
        try:
            result = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)).strip()
            if not result:
                raise ValueError("Empty response from LLM.")
            return result
        except Exception:
            logger.warning("Failed to extract keywords — falling back to contextual query.", exc_info=True)
            return None
