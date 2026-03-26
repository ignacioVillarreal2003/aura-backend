import logging
from typing import Optional
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.application.services.document_question_service.pipeline.document_question_pipeline_state import (
    DocumentQuestionPipelineState,
)
from app.infrastructure.document_context_provider.dtos.context_fragments_response import (
    ContextFragmentResponse,
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
from app.application.services.document_question_service.steps.generate_answer.generate_answer_settings import (
    GenerateAnswerSettings,
)
from app.application.services.document_question_service.steps.generate_answer.generate_answer_prompt import (
    GENERATE_ANSWER_PROMPT,
    LEARNING_GUIDELINES
)
from app.domain.constants.message_role import MessageRole

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
        return bool(state.rerank_fragments or state.retrieved_fragments)

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        context_fragments = state.rerank_fragments or state.retrieved_fragments

        context = "\n\n---\n\n".join(
            f.content for f in context_fragments
        )
        logger.debug(
            "Generating answer",
            extra={
                "fragment_count": len(context_fragments),
                "context_chars": len(context),
            },
        )

        history_tail = (
            state.history_messages[-self._settings.history_window:]
            if self._settings.history_window > 0
            else []
        )
        history_messages = []
        for msg in history_tail:
            if msg.role == MessageRole.human:
                history_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.assistant:
                history_messages.append(AIMessage(content=msg.content))

        prompt = [
            SystemMessage(content=LEARNING_GUIDELINES),
            *history_messages,
            HumanMessage(
                content=GENERATE_ANSWER_PROMPT.format(
                    query=state.current_message.content,
                    context=context,
                )
            ),
        ]

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
