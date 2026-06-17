from collections.abc import AsyncIterator
from typing import Optional

from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.streaming_generation_service import StreamingGenerationService
from app.application.services.user_interactions.document_action_service.document_action_prompts import (
    ANSWER_GUIDANCE,
    ANSWER_HUMAN_PROMPT,
    ANSWER_SYSTEM_PROMPT,
    DEFAULT_ANSWER_GUIDANCE,
    MAP_HUMAN_PROMPT,
    MAP_SYSTEM_PROMPT,
    REDUCE_HUMAN_PROMPT,
    REDUCE_SYSTEM_PROMPT,
)
from app.application.services.user_interactions.document_action_service.document_action_settings import (
    DocumentActionServiceSettings,
)
from app.application.services.user_interactions.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.user_interactions.document_action_service.interfaces.document_action_service_interface import (
    DocumentActionServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.dtos.user_interactions.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.user_interactions.document_action.document_action_response import DocumentActionResponse
from app.domain.dtos.user_interactions.document_action.document_action_stream_events import (
    DocumentActionStreamComplete,
    DocumentActionStreamDelta,
    DocumentActionStreamError,
    DocumentActionStreamEvent,
    DocumentActionStreamProgress,
)
from app.domain.field_limits import MAX_CONTENT_CHARS
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)


class DocumentActionService(
    StreamingGenerationService[DocumentActionRequest, DocumentActionResponse],
    DocumentActionServiceInterface,
):
    label = "document_action"
    exception_cls = DocumentActionServiceException
    unexpected_error_message = "Ocurrió un error inesperado al ejecutar la acción sobre el documento."
    generation_step_message = "Ejecutando la instrucción sobre el documento..."

    default_process_documents = True
    default_retrieve_context = False

    human_prompt = ANSWER_HUMAN_PROMPT
    map_system_prompt = MAP_SYSTEM_PROMPT
    map_human_prompt = MAP_HUMAN_PROMPT
    reduce_system_prompt = REDUCE_SYSTEM_PROMPT
    reduce_human_prompt = REDUCE_HUMAN_PROMPT

    stream_progress_event = DocumentActionStreamProgress
    stream_complete_event = DocumentActionStreamComplete
    stream_error_event = DocumentActionStreamError
    stream_delta_event = DocumentActionStreamDelta

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            document_action_settings: Optional[DocumentActionServiceSettings] = None,
    ) -> None:
        settings = document_action_settings or DocumentActionServiceSettings()
        super().__init__(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            ollama_llm_streaming_invoker=ollama_llm_streaming_invoker,
            document_context_provider=document_context_provider,
            generation_settings=settings.to_generation_settings(),
            attached_documents_settings=settings.to_attached_settings(),
            context_reduction_settings=settings.to_reduction_settings(),
        )

    def _request_messages(self, request: DocumentActionRequest) -> list[Message]:
        return [Message(role=MessageRole.human, content=request.instruction)]

    def _system_prompt(self, request: DocumentActionRequest) -> str:
        guidance = ANSWER_GUIDANCE.get(request.action, DEFAULT_ANSWER_GUIDANCE) if request.action \
            else DEFAULT_ANSWER_GUIDANCE
        return f"{ANSWER_SYSTEM_PROMPT}\n\n{guidance}"

    def _generation_progress_message(self, request: DocumentActionRequest) -> str:
        return self.generation_step_message

    def _request_log_extra(self, request: DocumentActionRequest) -> dict:
        return {
            "document_count": len(request.document_ids),
            "action": request.action.value if request.action else None,
            "retrieve_context": request.retrieve_context,
            "process_documents": request.process_documents,
        }

    def _postprocess_answer(self, answer: str) -> str:
        return answer[:MAX_CONTENT_CHARS]

    def _build_response(
            self,
            state: GenerationState,
            request: DocumentActionRequest,
            answer: str,
    ) -> DocumentActionResponse:
        return DocumentActionResponse(
            result=answer,
            document_ids=request.document_ids,
            instruction=request.instruction,
            action=request.action,
            fragments=state.all_fragments,
            degraded_stages=self._degraded_stages(state),
        )

    async def execute_document_action(
            self,
            document_action_request: DocumentActionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentActionResponse:
        return await self.generate(document_action_request, authenticated_user)

    async def execute_document_action_stream(
            self,
            document_action_request: DocumentActionRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[DocumentActionStreamEvent]:
        async for event in self.generate_stream(document_action_request, authenticated_user):
            yield event
