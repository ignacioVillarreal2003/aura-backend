import logging
from typing import Optional
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.services.document_question_service.steps.generate_answer.generate_answer_prompt import (
    GENERATE_ANSWER_PROMPT,
    GENERATE_ANSWER_SYSTEM_PROMPT,
    NO_INFO_SENTINEL,
)
from app.domain.constants.message_role import MessageRole
from app.application.services.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.application.services.document_question_service.pipeline.document_question_pipeline_resources import (
    DocumentQuestionPipelineResources,
)
from app.application.services.document_question_service.interfaces.document_question_plugin_interface import (
    DocumentQuestionPlugin,
)
from app.application.services.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
)
from app.application.services.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)

logger = logging.getLogger(__name__)


class GenerateAnswerPlugin(DocumentQuestionPlugin):
    def __init__(self, settings: Optional[DocumentQuestionServiceSettings] = None) -> None:
        self._settings = settings or DocumentQuestionServiceSettings()

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
            "Generating answer.",
            extra={
                "fragment_count": len(context_fragments),
                "context_chars": len(context),
            },
        )

        llm_input = self.build_generate_answer_llm_input(
            state,
            self._settings.generate_answer_history_window,
        )

        try:
            llm = await resources.ollama_llm_facade.get_llm_base()
            answer = await resources.llm_invoker.call_llm_content(
                llm=llm,
                llm_input=llm_input,
            )
        except DocumentQuestionServiceException:
            raise
        except Exception as e:
            logger.exception(
                "Failed to generate answer.",
                extra={"error_type": type(e).__name__},
            )
            raise DocumentQuestionServiceException(
                "Error invoking the language model"
            ) from e

        if not answer or not answer.strip():
            logger.warning("LLM returned an empty answer.")
            state.answer = ""
            return

        if NO_INFO_SENTINEL in answer:
            logger.debug("LLM indicated no relevant information found in context — redirecting to fallback.")
            state.answer = ""
            return

        logger.debug("Answer generated successfully.")
        state.answer = answer.strip()

    @staticmethod
    def build_generate_answer_llm_input(
            state: DocumentQuestionPipelineState,
            history_window: int,
    ) -> list[BaseMessage]:
        context_fragments = state.retrieved_fragments
        context = "\n\n---\n\n".join(f.content for f in context_fragments)

        history_tail = (
            state.history_messages[-history_window:]
            if history_window > 0
            else []
        )
        history_messages: list[BaseMessage] = []
        for msg in history_tail:
            if msg.role == MessageRole.human:
                history_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.assistant:
                history_messages.append(AIMessage(content=msg.content))

        return [
            SystemMessage(content=GENERATE_ANSWER_SYSTEM_PROMPT),
            *history_messages,
            HumanMessage(
                content=GENERATE_ANSWER_PROMPT.format(
                    query=state.current_message.content,
                    context=context,
                )
            ),
        ]
