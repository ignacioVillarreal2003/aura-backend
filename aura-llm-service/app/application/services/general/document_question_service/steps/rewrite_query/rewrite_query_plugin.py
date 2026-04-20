import logging
from typing import Optional
from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable

from app.application.services.general.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin
)
from app.application.services.general.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources
)
from app.application.services.general.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState
)
from app.application.services.general.document_question_service.steps.rewrite_query.rewrite_query_prompt import (
    CONTEXTUAL_QUESTION_PROMPT,
    KEYWORD_EXTRACTION_PROMPT
)
from app.application.services.general.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.domain.constants.message_role import MessageRole

logger = logging.getLogger(__name__)


class RewriteQueryPlugin(DocumentQuestionPlugin):
    _NO_HISTORY = "Sin historial previo."
    _HUMAN_LABEL = "Usuario"
    _ASSISTANT_LABEL = "Asistente"

    def __init__(self, settings: Optional[DocumentQuestionServiceSettings] = None) -> None:
        self._settings = settings or DocumentQuestionServiceSettings()

    @property
    def plugin_name(
            self
    ) -> str:
        return "rewrite_query"

    def should_run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources
    ) -> bool:
        return self._settings.rewrite_query_enabled

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        original_question = state.current_message.content
        llm = await resources.ollama_llm_facade.get_llm_base()

        contextual_question = await self._build_contextual_question(
            llm=llm,
            document_question_pipeline_resources=resources,
            original_question=original_question,
            document_question_pipeline_state=state,
        )
        state.question_with_history = contextual_question

        if self._settings.use_keywords:
            retrieval_keywords = await self._extract_keywords(
                llm=llm,
                document_question_pipeline_resources=resources,
                contextual_question=contextual_question,
                original_question=original_question,
            )
            state.retrieval_keywords = retrieval_keywords
        else:
            state.retrieval_keywords = None

    async def _build_contextual_question(
            self,
            llm: Runnable,
            document_question_pipeline_resources: DocumentQuestionPipelineResources,
            original_question: str,
            document_question_pipeline_state: DocumentQuestionPipelineState,
    ) -> str:
        history_text = self._format_history(document_question_pipeline_state)
        prompt = CONTEXTUAL_QUESTION_PROMPT.format(
            history=history_text,
            query=original_question,
        )
        try:
            raw = await document_question_pipeline_resources.llm_invoker.call_llm_content(
                llm=llm,
                llm_input=[HumanMessage(content=prompt)],
            )
            result = raw.strip()
            if not result:
                raise ValueError("Empty response from LLM")

            logger.debug(
                "Contextual question built",
                extra={"original": original_question, "contextual": result},
            )
            return result

        except Exception:
            logger.warning(
                "Failed to build contextual question, falling back to original",
                exc_info=True,
            )
            return original_question

    async def _extract_keywords(
            self,
            llm: Runnable,
            document_question_pipeline_resources: DocumentQuestionPipelineResources,
            contextual_question: str,
            original_question: str
    ) -> str:
        prompt = KEYWORD_EXTRACTION_PROMPT.format(
            contextual_question=contextual_question,
        )
        try:
            raw = await document_question_pipeline_resources.llm_invoker.call_llm_content(
                llm=llm,
                llm_input=[HumanMessage(content=prompt)],
            )
            result = raw.strip()
            if not result:
                raise ValueError("Empty response from LLM")

            logger.debug(
                "Retrieval keywords extracted",
                extra={"contextual": contextual_question, "keywords": result},
            )
            return result

        except Exception:
            logger.warning(
                "Failed to extract keywords, falling back to original question",
                exc_info=True,
            )
            return original_question

    def _format_history(
            self,
            state: DocumentQuestionPipelineState
    ) -> str:
        tail = state.history_messages[-self._settings.rewrite_query_history_window:]
        if not tail:
            return self._NO_HISTORY
        return "\n".join(
            f"{self._HUMAN_LABEL if msg.role == MessageRole.human else self._ASSISTANT_LABEL}: {msg.content}"
            for msg in tail
        )
