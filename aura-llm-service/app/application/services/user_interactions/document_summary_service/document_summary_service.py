import json
from collections.abc import AsyncIterator
from typing import Optional

from app.application.services.generation_shared.output_parsing import clean_text, split_markdown_doc
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.structured_generation_service import StructuredGenerationService
from app.application.services.user_interactions.document_summary_service.document_summary_prompts import (
    ANSWER_HUMAN_PROMPT,
    MAP_HUMAN_PROMPT,
    MAP_SYSTEM_PROMPT,
    REDUCE_HUMAN_PROMPT,
    REDUCE_SYSTEM_PROMPT,
    build_system_prompt,
)
from app.application.services.user_interactions.document_summary_service.document_summary_settings import (
    DocumentSummarySettings,
)
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.user_interactions.document_summary_service.exceptions.document_summary_service_exceptions import (
    DocumentSummaryServiceException,
)
from app.application.services.user_interactions.document_summary_service.interfaces.document_summary_service_interface import (
    DocumentSummaryServiceInterface,
)
from app.application.utils.llm_json_parser import parse_json_object
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.dtos.user_interactions.document_summary.document_summary_request import DocumentSummaryRequest
from app.domain.dtos.user_interactions.document_summary.document_summary_response import DocumentSummaryResponse
from app.domain.dtos.user_interactions.document_summary.document_summary_stream_events import (
    DocumentSummaryStreamComplete,
    DocumentSummaryStreamError,
    DocumentSummaryStreamEvent,
    DocumentSummaryStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

_SUMMARY_INSTRUCTION = "Generá un resumen estructurado, completo y fiel del documento adjunto."
_DEFAULT_TITLE = "Resumen de documentos"

_ParsedSummary = tuple[str, str, str]


class DocumentSummaryService(
    StructuredGenerationService[DocumentSummaryRequest, _ParsedSummary, DocumentSummaryResponse],
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

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: Optional[GenerationSettings] = None,
            document_summary_settings: Optional[DocumentSummarySettings] = None,
    ) -> None:
        super().__init__(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            document_context_provider=document_context_provider,
            generation_settings=generation_settings,
        )
        self._document_summary_settings = document_summary_settings or DocumentSummarySettings()

    def _request_messages(self, request: DocumentSummaryRequest) -> list[Message]:
        return [Message(role=MessageRole.human, content=_SUMMARY_INSTRUCTION)]

    def _system_prompt(self, request: DocumentSummaryRequest) -> str:
        return build_system_prompt(self._document_summary_settings)

    def _request_log_extra(self, request: DocumentSummaryRequest) -> dict:
        return {
            "document_count": len(request.document_ids),
            "retrieve_context": request.retrieve_context,
            "process_documents": request.process_documents,
        }

    def _parse_output(self, raw: str, request: DocumentSummaryRequest) -> _ParsedSummary:
        settings = self._document_summary_settings
        try:
            data = parse_json_object(raw)
            title = clean_text(data.get("title"), settings.max_title_chars)
            description = clean_text(data.get("description"), settings.max_description_chars)
            summary = clean_text(data.get("summary"), settings.max_summary_chars)
            if not summary:
                raise ValueError("Empty summary in JSON response.")
        except (json.JSONDecodeError, ValueError, TypeError):
            title, description, body = split_markdown_doc(raw)
            title = clean_text(title, settings.max_title_chars)
            description = clean_text(description, settings.max_description_chars)
            summary = clean_text(body or raw, settings.max_summary_chars)

        if not summary:
            raise DocumentSummaryServiceException(
                "No se pudo extraer el resumen de la respuesta del modelo.", status_code=502
            )
        return title or _DEFAULT_TITLE, description, summary

    def _result_log_extra(self, parsed: _ParsedSummary) -> dict:
        return {"summary_chars": len(parsed[2])}

    def _build_response(
            self,
            state: GenerationState,
            request: DocumentSummaryRequest,
            parsed: _ParsedSummary,
            raw: str,
    ) -> DocumentSummaryResponse:
        title, description, summary = parsed
        return DocumentSummaryResponse(
            title=title,
            description=description,
            summary=summary,
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
