import logging
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.document_question_service.document_question_state import (
    DocumentQuestionState,
)
from app.application.services.document_question_service.question_processor.question_processor_prompts import (
    BASE_QUESTION_SYSTEM_PROMPT,
    BASE_QUESTION_HUMAN_PROMPT,
    KEYWORD_QUESTION_SYSTEM_PROMPT,
    KEYWORD_QUESTION_HUMAN_PROMPT,
)
from app.application.services.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class QuestionProcessorPlugin:
    def __init__(
            self,
            settings: DocumentQuestionServiceSettings,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
    ) -> None:
        self._settings = settings
        self._ollama_llm_facade = ollama_llm_facade
        self._llm_invoker = llm_invoker
        self._document_context_provider = document_context_provider

    def _should_run(self) -> bool:
        return self._settings.question_processor_plugin_enabled

    async def run(self, document_question_state: DocumentQuestionState) -> None:
        if not self._should_run():
            return

        has_history = bool(document_question_state.history_messages)

        if has_history:
            document_question_state.base_question = await self._build_base_question(
                question=document_question_state.current_message.content,
                history_messages=document_question_state.history_messages,
            )

        if self._settings.use_keywords:
            document_question_state.keyword_question = await self._build_keywords_question(
                question=document_question_state.current_message.content,
                base_question=document_question_state.base_question,
            )

    async def _build_base_question(
            self,
            question: str,
            history_messages: list[Message],
    ) -> Optional[str]:
        llm = await self._ollama_llm_facade.get_llm_base()

        history_messages = self._format_history_messages(history_messages)

        llm_input = [
            SystemMessage(content=BASE_QUESTION_SYSTEM_PROMPT),
            HumanMessage(
                content=BASE_QUESTION_HUMAN_PROMPT.format(
                    history_messages=history_messages,
                    question=question,
                )
            ),
        ]

        try:
            result = await self._llm_invoker.call_llm_content(
                llm=llm,
                llm_input=llm_input,
            )
            result = result.strip()
            if not result:
                raise ValueError("Empty response from LLM.")

            logger.debug(
                "Contextual question built.",
                extra={"question": question, "base_question": result},
            )
            return result

        except Exception:
            logger.warning(
                "Failed to build contextual question — falling back to original.",
                exc_info=True,
            )
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
            HumanMessage(
                content=KEYWORD_QUESTION_HUMAN_PROMPT.format(
                    question=effective_question,
                )
            ),
        ]
        try:
            result = await self._llm_invoker.call_llm_content(
                llm=llm,
                llm_input=llm_input,
            )
            result = result.strip()
            if not result:
                raise ValueError("Empty response from LLM.")

            logger.debug(
                "Retrieval keywords extracted.",
                extra={"question": effective_question, "keyword_question": result},
            )
            return result

        except Exception:
            logger.warning(
                "Failed to extract keywords — falling back to contextual question.",
                exc_info=True,
            )
            return None

    def _format_history_messages(self, history_messages: list[Message]) -> str:
        tail = history_messages[-self._settings.question_processor_history_messages_window:]
        return "\n".join(
            f"{"Usuario" if msg.role == MessageRole.human else "Asistente"}: {msg.content}"
            for msg in tail
        )
