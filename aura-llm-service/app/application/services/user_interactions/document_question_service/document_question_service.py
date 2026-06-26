from collections.abc import AsyncIterator
from typing import Optional

from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.streaming_generation_service import StreamingGenerationService
from app.application.services.user_interactions.document_question_service.document_question_prompts import (
    ANSWER_HUMAN_PROMPT,
    MAP_HUMAN_PROMPT,
    MAP_SYSTEM_PROMPT,
    REDUCE_HUMAN_PROMPT,
    REDUCE_SYSTEM_PROMPT,
    build_system_prompt,
)
from app.application.services.user_interactions.document_question_service.document_question_settings import (
    DocumentQuestionServiceSettings,
)
from app.application.services.user_interactions.document_question_service.exceptions.document_question_service_exceptions import (
    DocumentQuestionServiceException,
)
from app.application.services.user_interactions.document_question_service.interfaces.document_question_service_interface import (
    DocumentQuestionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_MESSAGE_CONTENT_CHARS
from app.domain.dtos.user_interactions.document_question.document_question_request import DocumentQuestionRequest
from app.domain.dtos.user_interactions.document_question.document_question_response import DocumentQuestionResponse
from app.domain.dtos.user_interactions.document_question.document_question_stream_events import (
    DocumentQuestionStreamComplete,
    DocumentQuestionStreamDelta,
    DocumentQuestionStreamError,
    DocumentQuestionStreamEvent,
    DocumentQuestionStreamMeta,
    DocumentQuestionStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)


class DocumentQuestionService(
    StreamingGenerationService[DocumentQuestionRequest, DocumentQuestionResponse],
    DocumentQuestionServiceInterface,
):
    label = "document_question"
    exception_cls = DocumentQuestionServiceException
    unexpected_error_message = "Ocurrió un error inesperado al procesar la consulta."
    generation_step_message = "Elaborando la respuesta con base en la documentación..."

    default_retrieve_context = True
    default_process_documents = False
    summarize_history = True

    human_prompt = ANSWER_HUMAN_PROMPT
    map_system_prompt = MAP_SYSTEM_PROMPT
    map_human_prompt = MAP_HUMAN_PROMPT
    reduce_system_prompt = REDUCE_SYSTEM_PROMPT
    reduce_human_prompt = REDUCE_HUMAN_PROMPT

    stream_progress_event = DocumentQuestionStreamProgress
    stream_complete_event = DocumentQuestionStreamComplete
    stream_error_event = DocumentQuestionStreamError
    stream_delta_event = DocumentQuestionStreamDelta

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            document_question_settings: Optional[DocumentQuestionServiceSettings] = None,
    ) -> None:
        settings = document_question_settings or DocumentQuestionServiceSettings()
        self._document_question_settings = settings
        super().__init__(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            ollama_llm_streaming_invoker=ollama_llm_streaming_invoker,
            document_context_provider=document_context_provider,
            generation_settings=settings.to_generation_settings(),
            query_reformulation_settings=settings.to_reformulation_settings(),
            context_retrieval_settings=settings.to_retrieval_settings(),
            attached_documents_settings=settings.to_attached_settings(),
            context_reduction_settings=settings.to_reduction_settings(),
            section_context_settings=settings.to_section_settings(),
        )

    def _system_prompt(self, request: DocumentQuestionRequest) -> str:
        return build_system_prompt(self._document_question_settings)

    def _request_log_extra(self, request: DocumentQuestionRequest) -> dict:
        return {
            "document_count": len(request.document_ids),
            "retrieve_context": request.retrieve_context,
            "process_documents": request.process_documents,
        }

    def _response_char_limit(self) -> int:
        return self._document_question_settings.max_response_chars

    def _build_response(
            self,
            state: GenerationState,
            request: DocumentQuestionRequest,
            answer: str,
    ) -> DocumentQuestionResponse:
        return DocumentQuestionResponse(
            question=state.current_message.content,
            answer=answer,
            messages=[
                *state.messages,
                Message(role=MessageRole.assistant, content=answer[:MAX_MESSAGE_CONTENT_CHARS]),
            ],
            fragments=state.all_fragments,
            degraded_stages=self._degraded_stages(state),
        )

    async def _stream_pre_generation_events(
            self,
            state: GenerationState,
            request: DocumentQuestionRequest,
    ) -> AsyncIterator[DocumentQuestionStreamMeta]:
        yield DocumentQuestionStreamMeta(
            question=state.current_message.content,
            fragments=list(state.all_fragments),
        )

    async def execute_document_question(
            self,
            document_question_request: DocumentQuestionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentQuestionResponse:
        return await self.generate(document_question_request, authenticated_user)

    async def execute_document_question_stream(
            self,
            document_question_request: DocumentQuestionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[DocumentQuestionStreamEvent]:
        async for event in self.generate_stream(document_question_request, authenticated_user):
            yield event
