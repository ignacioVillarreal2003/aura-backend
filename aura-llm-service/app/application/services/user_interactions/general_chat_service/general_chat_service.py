from collections.abc import AsyncIterator
from typing import Optional

from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.streaming_generation_service import StreamingGenerationService
from app.application.services.user_interactions.general_chat_service.general_chat_prompt import (
    ANSWER_HUMAN_PROMPT,
    MAP_HUMAN_PROMPT,
    MAP_SYSTEM_PROMPT,
    REDUCE_HUMAN_PROMPT,
    REDUCE_SYSTEM_PROMPT,
    build_system_prompt,
)
from app.application.services.user_interactions.general_chat_service.exceptions.general_chat_service_exceptions import (
    GeneralChatServiceException,
)
from app.application.services.user_interactions.general_chat_service.interfaces.general_chat_service_interface import (
    GeneralChatServiceInterface,
)
from app.application.services.user_interactions.general_chat_service.general_chat_settings import GeneralChatSettings
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.field_limits import MAX_MESSAGE_CONTENT_CHARS
from app.domain.dtos.user_interactions.general_chat.general_chat_request import GeneralChatRequest
from app.domain.dtos.user_interactions.general_chat.general_chat_response import GeneralChatResponse
from app.domain.dtos.user_interactions.general_chat.general_chat_stream_events import (
    GeneralChatStreamComplete,
    GeneralChatStreamDelta,
    GeneralChatStreamError,
    GeneralChatStreamEvent,
    GeneralChatStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)


class GeneralChatService(
    StreamingGenerationService[GeneralChatRequest, GeneralChatResponse],
    GeneralChatServiceInterface,
):
    label = "general_chat"
    exception_cls = GeneralChatServiceException
    unexpected_error_message = "Error inesperado al procesar la solicitud de chat."
    generation_step_message = "Elaborando la respuesta..."

    default_retrieve_context = False
    default_process_documents = False
    summarize_history = True

    human_prompt = ANSWER_HUMAN_PROMPT
    map_system_prompt = MAP_SYSTEM_PROMPT
    map_human_prompt = MAP_HUMAN_PROMPT
    reduce_system_prompt = REDUCE_SYSTEM_PROMPT
    reduce_human_prompt = REDUCE_HUMAN_PROMPT

    stream_progress_event = GeneralChatStreamProgress
    stream_complete_event = GeneralChatStreamComplete
    stream_error_event = GeneralChatStreamError
    stream_delta_event = GeneralChatStreamDelta

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            general_chat_settings: Optional[GeneralChatSettings] = None,
    ) -> None:
        self._general_chat_settings = general_chat_settings or GeneralChatSettings()
        super().__init__(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            ollama_llm_streaming_invoker=ollama_llm_streaming_invoker,
            document_context_provider=document_context_provider,
        )

    def _system_prompt(self, request: GeneralChatRequest) -> str:
        return build_system_prompt(self._general_chat_settings)

    def _request_log_extra(self, request: GeneralChatRequest) -> dict:
        return {
            "document_count": len(request.document_ids),
            "retrieve_context": request.retrieve_context,
            "process_documents": request.process_documents,
        }

    def _response_char_limit(self) -> int:
        return self._general_chat_settings.max_response_chars

    def _build_response(
            self,
            state: GenerationState,
            request: GeneralChatRequest,
            answer: str,
    ) -> GeneralChatResponse:
        return GeneralChatResponse(
            answer=answer,
            messages=[
                *state.messages,
                Message(role=MessageRole.assistant, content=answer[:MAX_MESSAGE_CONTENT_CHARS]),
            ],
            fragments=state.all_fragments,
            degraded_stages=self._degraded_stages(state),
        )

    async def execute_general_chat(
            self,
            general_chat_request: GeneralChatRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GeneralChatResponse:
        return await self.generate(general_chat_request, authenticated_user)

    async def execute_general_chat_stream(
            self,
            general_chat_request: GeneralChatRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[GeneralChatStreamEvent]:
        async for event in self.generate_stream(general_chat_request, authenticated_user):
            yield event
