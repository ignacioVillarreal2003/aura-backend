import logging
import re
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
from app.application.services.document_question_service.prompts.query_rewrite_prompt import (
    QUERY_REWRITE_PROMPT,
)
from app.domain.constants.message_role import MessageRole

logger = logging.getLogger(__name__)


class RewriteQueryPlugin(DocumentQuestionPlugin):
    @property
    def plugin_name(self) -> str:
        return "rewrite_query"

    def should_run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> bool:
        return resources.settings.query_rewrite_enabled

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        current_question = state.current_message.content
        if not resources.settings.query_rewrite_enabled:
            state.effective_query = current_question
            return

        try:
            history_tail = state.history_messages[-resources.settings.history_window:]
            history_text = "\n".join(
                [
                    f"{'Usuario' if msg.role == MessageRole.human else 'Asistente'}: {msg.content}"
                    for msg in history_tail
                ]
            )
            content = QUERY_REWRITE_PROMPT.format(
                history=history_text or "Sin historial previo.",
                query=current_question,
            )
            prompt = [HumanMessage(content=content)]
            llm = await resources.ollama_llm_facade.get_llm_base()
            rewritten = await resources.llm_invoker.call_llm_content(
                llm=llm,
                llm_input=prompt,
            )
            rewritten = self._sanitize_rewritten_query(rewritten)

            if rewritten and rewritten.strip():
                logger.debug(
                    "Query rewritten",
                    extra={"original": current_question, "rewritten": rewritten.strip()},
                )
                state.effective_query = rewritten.strip()
                return

            logger.warning("Query rewrite returned empty result, using original")
            state.effective_query = current_question
        except Exception:
            logger.warning(
                "Query rewrite failed, falling back to original question",
                exc_info=True,
            )
            state.effective_query = current_question

    @staticmethod
    def _sanitize_rewritten_query(raw: str) -> str:
        if not raw:
            return ""

        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            return ""

        cleaned_lines: list[str] = []
        for line in lines:
            normalized = re.sub(
                r"^\s*(la\s+consulta\s+optimizada\s+ser[ií]a\s*:|consulta\s+optimizada\s*:)\s*",
                "",
                line,
                flags=re.IGNORECASE,
            )
            normalized = normalized.strip().strip('"').strip("'").strip()
            normalized = re.sub(r"^[-*]\s+", "", normalized)
            normalized = normalized.strip()
            if normalized:
                cleaned_lines.append(normalized)

        if not cleaned_lines:
            return ""

        # Prefer the longest cleaned line; usually it contains the full optimized query.
        candidate = max(cleaned_lines, key=len)
        return candidate
