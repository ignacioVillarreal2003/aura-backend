import logging
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable

from app.application.services.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.document_question_service.steps.rewrite_query.rewrite_query_prompt import (
    CONTEXTUAL_QUESTION_PROMPT,
    CONTEXTUAL_QUESTION_SYSTEM_PROMPT,
    KEYWORD_EXTRACTION_PROMPT,
    KEYWORD_EXTRACTION_SYSTEM_PROMPT,
)
from app.application.services.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.domain.constants.message_role import MessageRole
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import \
    DocumentContextProviderInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)


class QuestionProcessorPlugin:
    def __init__(
            self,
            settings: DocumentQuestionServiceSettings,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface
    ) -> None:
        self._settings = settings
        self._ollama_llm_facade = ollama_llm_facade
        self._llm_invoker = llm_invoker
        self._document_context_provider = document_context_provider

    def _should_run(self) -> bool:
        return self._settings.question_processor_plugin_enabled

    async def run(self, document_question_pipeline_state: DocumentQuestionPipelineState) -> None:
        if not self._should_run():
            return

        question = document_question_pipeline_state.current_message.content
        llm = await resources.ollama_llm_facade.get_llm_base()

        has_history = bool(state.history_messages)

        if has_history:
            contextual_question = await self._build_contextual_question(
                llm=llm,
                resources=resources,
                original_question=original_question,
                state=state,
            )
        else:
            logger.debug("No conversation history — skipping contextual rewrite.")
            contextual_question = original_question

        state.question_with_history = contextual_question

        if self._settings.use_keywords:
            retrieval_keywords = await self._extract_keywords(
                llm=llm,
                resources=resources,
                contextual_question=contextual_question,
                original_question=original_question,
            )
            state.retrieval_keywords = retrieval_keywords
        else:
            state.retrieval_keywords = None

    async def _build_contextual_question(
            self,
            llm: Runnable,
            resources: DocumentQuestionPipelineResources,
            original_question: str,
            state: DocumentQuestionPipelineState,
    ) -> str:
        history_text = self._format_history(state)
        llm_input = [
            SystemMessage(content=CONTEXTUAL_QUESTION_SYSTEM_PROMPT),
            HumanMessage(
                content=CONTEXTUAL_QUESTION_PROMPT.format(
                    history=history_text,
                    query=original_question,
                )
            ),
        ]
        try:
            raw = await resources.llm_invoker.call_llm_content(
                llm=llm,
                llm_input=llm_input,
            )
            result = raw.strip()
            if not result:
                raise ValueError("Empty response from LLM.")

            logger.debug(
                "Contextual question built.",
                extra={"original": original_question, "contextual": result},
            )
            return result

        except Exception:
            logger.warning(
                "Failed to build contextual question — falling back to original.",
                exc_info=True,
            )
            return original_question

    async def _extract_keywords(
            self,
            llm: Runnable,
            resources: DocumentQuestionPipelineResources,
            contextual_question: str,
            original_question: str,
    ) -> str:
        llm_input = [
            SystemMessage(content=KEYWORD_EXTRACTION_SYSTEM_PROMPT),
            HumanMessage(
                content=KEYWORD_EXTRACTION_PROMPT.format(
                    contextual_question=contextual_question,
                )
            ),
        ]
        try:
            raw = await resources.llm_invoker.call_llm_content(
                llm=llm,
                llm_input=llm_input,
            )
            result = raw.strip()
            if not result:
                raise ValueError("Empty response from LLM.")

            logger.debug(
                "Retrieval keywords extracted.",
                extra={"contextual": contextual_question, "keywords": result},
            )
            return result

        except Exception:
            logger.warning(
                "Failed to extract keywords — falling back to contextual question.",
                exc_info=True,
            )
            return contextual_question

    _HUMAN_LABEL = "Usuario"
    _ASSISTANT_LABEL = "Asistente"

    def _format_history(
            self,
            state: DocumentQuestionPipelineState,
    ) -> str:
        tail = state.history_messages[-self._settings.rewrite_query_history_window:]
        return "\n".join(
            f"{self._HUMAN_LABEL if msg.role == MessageRole.human else self._ASSISTANT_LABEL}: {msg.content}"
            for msg in tail
        )
