import logging
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

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
from app.application.services.document_question_service.prompts.default_style_prompt import (
    LEARNING_GUIDELINES,
)
from app.application.services.document_question_service.prompts.generation_prompt import (
    GENERATION_PROMPT,
)
from app.domain.constants.message_role import MessageRole

logger = logging.getLogger(__name__)


class GenerateAnswerPlugin(DocumentQuestionPlugin):
    @property
    def plugin_name(self) -> str:
        return "generate_answer"

    def should_run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> bool:
        return True

    async def run(
            self,
            state: DocumentQuestionPipelineState,
            resources: DocumentQuestionPipelineResources,
    ) -> None:
        if not state.retrieved_fragments:
            state.response = ""
            return

        style_block = (
            f"{LEARNING_GUIDELINES}\n\n"
        )
        context = "\n\n---\n\n".join(state.retrieved_fragments)
        history_tail = state.history_messages[-resources.settings.history_window:]
        history_messages = []
        for msg in history_tail:
            if msg.role == MessageRole.human:
                history_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.assistant:
                history_messages.append(AIMessage(content=msg.content))

        prompt = [
            SystemMessage(content=style_block),
            *history_messages,
            HumanMessage(
                content=GENERATION_PROMPT.format(
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
            state.response = ""
            return

        logger.debug("Answer generated successfully")
        state.response = answer.strip()
