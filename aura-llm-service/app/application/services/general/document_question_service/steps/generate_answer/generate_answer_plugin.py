import logging
from typing import Optional

from app.application.services.general.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.general.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.general.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)
from app.application.services.general.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
)
from app.application.services.general.document_question_service.steps.generate_answer.generate_answer_llm_input import (
    build_generate_answer_llm_input,
)
from app.application.services.general.document_question_service.steps.generate_answer.generate_answer_settings import (
    GenerateAnswerSettings,
)

logger = logging.getLogger(__name__)


class GenerateAnswerPlugin(DocumentQuestionPlugin):
    def __init__(self, generate_answer_settings: Optional[GenerateAnswerSettings] = None) -> None:
        self._settings = generate_answer_settings or GenerateAnswerSettings()

    @property
    def plugin_name(self) -> str:
        return "generate_answer"

    def should_run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> bool:
        return bool(state.retrieved_fragments)

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        context_fragments = state.retrieved_fragments
        context = "\n\n---\n\n".join(f.content for f in context_fragments)
        logger.debug(
            "Generating answer",
            extra={
                "fragment_count": len(context_fragments),
                "context_chars": len(context),
            },
        )

        prompt = build_generate_answer_llm_input(
            state,
            self._settings.history_window,
        )

        try:
            llm = await resources.ollama_llm_facade.get_llm_base()
            answer = await resources.llm_invoker.call_llm_content(
                llm=llm,
                llm_input=prompt,
            )
        except DocumentQuestionServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to generate answer",
                extra={"error_type": type(e).__name__},
            )
            raise DocumentQuestionServiceException(
                "Error invoking the language model"
            ) from e

        if not answer or not answer.strip():
            logger.warning("LLM returned an empty answer")
            state.answer = ""
            return

        logger.debug("Answer generated successfully")
        state.answer = answer.strip()
