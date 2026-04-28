import logging
from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)
from app.application.services.document_question_service.steps.fallback_answer.fallback_answer_prompt import (
    FALLBACK_ANSWER_PROMPT,
    FALLBACK_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class FallbackAnswerPlugin(DocumentQuestionPlugin):
    @property
    def plugin_name(self) -> str:
        return "fallback_answer"

    def should_run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> bool:
        has_context = bool(state.retrieved_fragments)
        has_answer = bool(state.answer and state.answer.strip())
        return not has_context or not has_answer

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        has_context = bool(state.retrieved_fragments)
        reason = "no context retrieved" if not has_context else "generate_answer returned empty"
        logger.debug("Fallback triggered", extra={"reason": reason})

        try:
            prompt = [
                SystemMessage(content=FALLBACK_SYSTEM_PROMPT),
                HumanMessage(content=FALLBACK_ANSWER_PROMPT.format(query=state.current_message.content)),
            ]
            llm = await resources.ollama_llm_facade.get_llm_base()
            answer = await resources.llm_invoker.call_llm_content(
                llm=llm,
                llm_input=prompt,
            )

            if answer and answer.strip():
                state.answer = answer.strip()
                return
        except Exception:
            logger.warning("Fallback generation failed, returning static message", exc_info=True)

        state.answer = (
            "No se encontró información relevante en la base documental para responder su consulta. "
            "Por favor, reformule su pregunta o consulte directamente la documentación disponible."
        )
