import logging
from typing import Optional
from langchain_core.messages import HumanMessage

from app.application.services.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)
from app.application.services.document_question_service.steps.rewrite_query.rewrite_query_prompt import (
    REWRITE_QUERY_PROMPT,
)
from app.application.services.document_question_service.steps.rewrite_query.rewrite_query_settings import (
    QueryRewriteSettings,
)
from app.domain.constants.message_role import MessageRole

logger = logging.getLogger(__name__)


class RewriteQueryPlugin(DocumentQuestionPlugin):
    def __init__(self, query_rewrite_settings: Optional[QueryRewriteSettings] = None) -> None:
        self._settings = query_rewrite_settings or QueryRewriteSettings()

    @property
    def plugin_name(self) -> str:
        return "rewrite_query"

    def should_run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> bool:
        return self._settings.enabled

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        current_question = state.current_message.content

        try:
            history_tail = state.history_messages[-self._settings.history_window:]
            history_text = "\n".join(
                f"{'Usuario' if msg.role == MessageRole.human else 'Asistente'}: {msg.content}"
                for msg in history_tail
            )
            content = REWRITE_QUERY_PROMPT.format(
                history=history_text or "Sin historial previo.",
                query=current_question,
            )
            llm = await resources.ollama_llm_facade.get_llm_base()
            raw = await resources.llm_invoker.call_llm_content(
                llm=llm,
                llm_input=[HumanMessage(content=content)],
            )
            rewritten = self._sanitize_rewritten_query(raw)

            if rewritten:
                logger.debug(
                    "Query rewritten",
                    extra={"original": current_question, "rewritten": rewritten},
                )
                state.retrieval_query = rewritten
                return

            logger.warning("Query rewrite returned empty result, using original")
            state.retrieval_query = current_question

        except Exception:
            logger.warning(
                "Query rewrite failed, falling back to original question",
                exc_info=True,
            )
            state.retrieval_query = current_question

    @staticmethod
    def _sanitize_rewritten_query(raw: str) -> str:
        return raw.strip()
