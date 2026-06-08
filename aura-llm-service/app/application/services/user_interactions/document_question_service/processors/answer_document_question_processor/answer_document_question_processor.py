import logging
from collections.abc import AsyncIterator
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.application.services.user_interactions.document_question_service.processors.answer_document_question_processor.answer_document_question_prompt import (
    ANSWER_SYSTEM_PROMPT,
    ANSWER_HUMAN_PROMPT,
)
from app.application.services.user_interactions.document_question_service.document_question_state import DocumentQuestionState
from app.domain.constants.message_role import MessageRole
from app.application.services.user_interactions.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
)
from app.application.services.user_interactions.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.domain.dtos.user_interactions.document_question.document_question_stream_events import DocumentQuestionStreamDelta
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)

logger = logging.getLogger(__name__)


class AnswerDocumentQuestionProcessor:
    def __init__(
            self,
            document_question_service_settings: DocumentQuestionServiceSettings,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
    ) -> None:
        self._settings = document_question_service_settings
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._ollama_llm_streaming_invoker = ollama_llm_streaming_invoker

    async def run(self, document_question_state: DocumentQuestionState) -> None:
        if not document_question_state.all_fragments and not document_question_state.reduced_attached_context:
            return

        llm_input = self.build_llm_input(
            document_question_state=document_question_state,
            history_messages_window=self._settings.history_messages_window,
            max_context_chars=self._settings.max_context_chars,
        )

        try:
            llm = await self._ollama_llm_facade.get_llm_base()
            answer = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
        except DocumentQuestionServiceException:
            raise
        except Exception as e:
            logger.exception("Failed to generate answer.", extra={"error_type": type(e).__name__})
            raise DocumentQuestionServiceException("Error invoking the language model") from e

        if answer and answer.strip():
            document_question_state.answer = answer.strip()
        else:
            logger.warning("LLM returned an empty answer.")

    async def stream(
            self,
            document_question_state: DocumentQuestionState,
    ) -> AsyncIterator[DocumentQuestionStreamDelta]:
        if not document_question_state.all_fragments and not document_question_state.reduced_attached_context:
            return

        llm_input = self.build_llm_input(
            document_question_state=document_question_state,
            history_messages_window=self._settings.history_messages_window,
            max_context_chars=self._settings.max_context_chars,
        )
        llm = await self._ollama_llm_facade.get_llm_base()

        async for delta in self._ollama_llm_streaming_invoker.stream_llm_content(llm, llm_input):
            document_question_state.answer += delta
            yield DocumentQuestionStreamDelta(text=delta)

        if not document_question_state.answer.strip():
            logger.warning(
                "LLM stream produced no visible text; invoking same prompt without stream",
                extra={"fragment_count": len(document_question_state.all_fragments)},
            )
            non_stream_answer = await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_input)
            if non_stream_answer and non_stream_answer.strip():
                document_question_state.answer = non_stream_answer.strip()
                yield DocumentQuestionStreamDelta(text=document_question_state.answer)

    @staticmethod
    def build_llm_input(
            document_question_state: DocumentQuestionState,
            history_messages_window: int,
            max_context_chars: int = 12_000,
    ) -> list[BaseMessage]:
        if document_question_state.reduced_attached_context:
            attached_ids = {f.id for f in document_question_state.attached_fragments}
            rag_only = [f for f in document_question_state.fragments if f.id not in attached_ids]
            parts = [document_question_state.reduced_attached_context]
            parts.extend(f.content for f in rag_only)
            context = "\n\n---\n\n".join(p for p in parts if p)
        else:
            context = "\n\n---\n\n".join(f.content for f in document_question_state.all_fragments)
        if len(context) > max_context_chars:
            context = context[:max_context_chars]

        tail = (
            document_question_state.history_messages[-history_messages_window:]
            if history_messages_window > 0
            else []
        )
        history: list[BaseMessage] = []
        for msg in tail:
            if msg.role == MessageRole.human:
                history.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.assistant:
                history.append(AIMessage(content=msg.content))

        return [
            SystemMessage(content=ANSWER_SYSTEM_PROMPT),
            *history,
            HumanMessage(
                content=ANSWER_HUMAN_PROMPT.format(
                    question=document_question_state.current_message.content,
                    context=context,
                )
            ),
        ]
