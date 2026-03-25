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
from app.application.services.document_question_service.prompts.default_style_prompt import (
    CONCISE_MODE,
    EXPLANATORY_MODE,
    FORMAL_MODE,
    LEARNING_GUIDELINES,
)
from app.application.services.document_question_service.prompts.fallback_prompt import (
    FALLBACK_PROMPT,
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
        return (not state.retrieved_fragments) or (not state.response or not state.response.strip())

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        try:
            style_block = (
                f"{LEARNING_GUIDELINES}\n\n"
                f"{CONCISE_MODE}\n\n"
                f"{EXPLANATORY_MODE}\n\n"
                f"{FORMAL_MODE}"
            )
            prompt = [
                SystemMessage(content=style_block),
                HumanMessage(content=FALLBACK_PROMPT.format(query=state.current_message.content)),
            ]
            llm = await resources.ollama_llm_facade.get_llm_base()
            answer = await resources.llm_invoker.call_llm_content(
                llm=llm,
                llm_input=prompt,
            )

            if answer and answer.strip():
                state.response = answer.strip()
                return
        except Exception:
            logger.warning("Fallback generation failed, returning static message", exc_info=True)

        state.response = (
            "No se encontró información relevante en la base documental para responder su consulta. "
            "Por favor, reformule su pregunta o consulte directamente la documentación disponible."
        )
