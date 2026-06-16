from collections.abc import AsyncIterator
from typing import Optional

from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.streaming_generation_service import StreamingGenerationService
from app.application.services.user_interactions.document_summary_service.document_summary_prompts import (
    ANSWER_HUMAN_PROMPT,
    ANSWER_SYSTEM_PROMPT,
    MAP_HUMAN_PROMPT,
    MAP_SYSTEM_PROMPT,
    REDUCE_HUMAN_PROMPT,
    REDUCE_SYSTEM_PROMPT,
)
from app.application.services.user_interactions.document_summary_service.document_summary_settings import (
    DocumentSummaryServiceSettings,
)
from app.application.services.user_interactions.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException,
)
from app.application.services.user_interactions.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.dtos.user_interactions.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.user_interactions.document_summary.document_summary_response import DocumentSummaryResponse
from app.domain.dtos.user_interactions.document_summary.document_summary_stream_events import (
    DocumentSummaryStreamComplete,
    DocumentSummaryStreamDelta,
    DocumentSummaryStreamError,
    DocumentSummaryStreamEvent,
    DocumentSummaryStreamProgress,
)
from app.domain.field_limits import MAX_SUMMARY_CHARS
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_streaming_invoker_interface import (
    OllamaLLMStreamingInvokerInterface,
)

_SUMMARY_INSTRUCTION = "Generá un resumen estructurado, completo y fiel del documento adjunto."


class DocumentSummaryService(
    StreamingGenerationService[DocumentSummaryRequest, DocumentSummaryResponse],
    DocumentSummaryServiceInterface,
):
    label = "document_summary"
    exception_cls = DocumentSummaryServiceException
    unexpected_error_message = "Ocurrió un error inesperado al generar el resumen del documento."
    generation_step_message = "Analizando y resumiendo el documento..."

    default_process_documents = True
    default_retrieve_context = False

    human_prompt = ANSWER_HUMAN_PROMPT
    map_system_prompt = MAP_SYSTEM_PROMPT
    map_human_prompt = MAP_HUMAN_PROMPT
    reduce_system_prompt = REDUCE_SYSTEM_PROMPT
    reduce_human_prompt = REDUCE_HUMAN_PROMPT

    stream_progress_event = DocumentSummaryStreamProgress
    stream_complete_event = DocumentSummaryStreamComplete
    stream_error_event = DocumentSummaryStreamError
    stream_delta_event = DocumentSummaryStreamDelta

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            ollama_llm_streaming_invoker: OllamaLLMStreamingInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            document_summary_settings: Optional[DocumentSummaryServiceSettings] = None,
    ) -> None:
        settings = document_summary_settings or DocumentSummaryServiceSettings()
        super().__init__(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            ollama_llm_streaming_invoker=ollama_llm_streaming_invoker,
            document_context_provider=document_context_provider,
            generation_settings=settings.to_generation_settings(),
            attached_documents_settings=settings.to_attached_settings(),
            context_reduction_settings=settings.to_reduction_settings(),
        )

    def _request_messages(self, request: DocumentSummaryRequest) -> list[Message]:
        return [Message(role=MessageRole.human, content=_SUMMARY_INSTRUCTION)]

    def _system_prompt(self, request: DocumentSummaryRequest) -> str:
        return ANSWER_SYSTEM_PROMPT

    def _request_log_extra(self, request: DocumentSummaryRequest) -> dict:
        return {
            "document_count": len(request.document_ids),
            "retrieve_context": request.retrieve_context,
            "process_documents": request.process_documents,
        }

    def _postprocess_answer(self, answer: str) -> str:
        return answer[:MAX_SUMMARY_CHARS]

    def _build_response(
            self,
            state: GenerationState,
            request: DocumentSummaryRequest,
            answer: str,
    ) -> DocumentSummaryResponse:
        return DocumentSummaryResponse(
            document_ids=request.document_ids,
            summary=answer,
            fragments=state.all_fragments,
            degraded_stages=self._degraded_stages(state),
        )

    async def execute_document_summary(
            self,
            document_summary_request: DocumentSummaryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> DocumentSummaryResponse:
        return await self.generate(document_summary_request, authenticated_user)

    async def execute_document_summary_stream(
            self,
            document_summary_request: DocumentSummaryRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[DocumentSummaryStreamEvent]:
        async for event in self.generate_stream(document_summary_request, authenticated_user):
            yield event
