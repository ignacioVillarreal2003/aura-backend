import json
from collections.abc import AsyncIterator
from typing import Optional

from app.application.services.generation_shared.output_parsing import clean_text, split_markdown_doc
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.structured_generation_service import StructuredGenerationService
from app.application.services.user_interactions.document_action_service.document_action_prompts import (
    ANSWER_HUMAN_PROMPT,
    MAP_HUMAN_PROMPT,
    MAP_SYSTEM_PROMPT,
    REDUCE_HUMAN_PROMPT,
    REDUCE_SYSTEM_PROMPT,
    build_system_prompt,
)
from app.application.services.user_interactions.document_action_service.document_action_settings import (
    DocumentActionSettings,
)
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.user_interactions.document_action_service.exceptions.document_action_service_exceptions import (
    DocumentActionServiceException,
)
from app.application.services.user_interactions.document_action_service.interfaces.document_action_service_interface import (
    DocumentActionServiceInterface,
)
from app.application.utils.llm_json_parser import parse_json_object
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.message import Message
from app.domain.dtos.user_interactions.document_action.document_action_request import DocumentActionRequest
from app.domain.dtos.user_interactions.document_action.document_action_response import DocumentActionResponse
from app.domain.dtos.user_interactions.document_action.document_action_stream_events import (
    DocumentActionStreamComplete,
    DocumentActionStreamError,
    DocumentActionStreamEvent,
    DocumentActionStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

_DEFAULT_TITLE = "Resultado de la acción"

_ParsedAction = tuple[str, str, str]


class DocumentActionService(
    StructuredGenerationService[DocumentActionRequest, _ParsedAction, DocumentActionResponse],
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

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: Optional[GenerationSettings] = None,
            document_action_settings: Optional[DocumentActionSettings] = None,
    ) -> None:
        super().__init__(
            ollama_llm_facade=ollama_llm_facade,
            ollama_llm_invoker=ollama_llm_invoker,
            document_context_provider=document_context_provider,
            generation_settings=generation_settings,
        )
        self._document_action_settings = document_action_settings or DocumentActionSettings()

    def _request_messages(self, request: DocumentActionRequest) -> list[Message]:
        return [Message(role=MessageRole.human, content=request.instruction)]

    def _system_prompt(self, request: DocumentActionRequest) -> str:
        return build_system_prompt(request.action, self._document_action_settings)

    def _request_log_extra(self, request: DocumentActionRequest) -> dict:
        return {
            "document_count": len(request.document_ids),
            "action": request.action.value if request.action else None,
            "retrieve_context": request.retrieve_context,
            "process_documents": request.process_documents,
        }

    def _parse_output(self, raw: str, request: DocumentActionRequest) -> _ParsedAction:
        settings = self._document_action_settings
        try:
            data = parse_json_object(raw)
            title = clean_text(data.get("title"), settings.max_title_chars)
            description = clean_text(data.get("description"), settings.max_description_chars)
            result = clean_text(data.get("result"), settings.max_result_chars)
            if not result:
                raise ValueError("Empty result in JSON response.")
        except (json.JSONDecodeError, ValueError, TypeError):
            title, description, body = split_markdown_doc(raw)
            title = clean_text(title, settings.max_title_chars)
            description = clean_text(description, settings.max_description_chars)
            result = clean_text(body or raw, settings.max_result_chars)

        if not result:
            raise DocumentActionServiceException(
                "No se pudo extraer el resultado de la respuesta del modelo.", status_code=502
            )
        return title or _DEFAULT_TITLE, description, result

    def _result_log_extra(self, parsed: _ParsedAction) -> dict:
        return {"result_chars": len(parsed[2])}

    def _build_response(
            self,
            state: GenerationState,
            request: DocumentActionRequest,
            parsed: _ParsedAction,
            raw: str,
    ) -> DocumentActionResponse:
        title, description, result = parsed
        return DocumentActionResponse(
            title=title,
            description=description,
            result=result,
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
