import json
import logging

from app.application.utils.llm_json_parser import parse_json_object
from app.application.services.user_interactions.checklist_service.checklist_prompt import (
    MAP_HUMAN_PROMPT,
    MAP_SYSTEM_PROMPT,
    REDUCE_HUMAN_PROMPT,
    REDUCE_SYSTEM_PROMPT,
    HUMAN_PROMPT,
    build_system_prompt,
)
from app.application.services.user_interactions.checklist_service.exceptions.checklist_service_exceptions import (
    ChecklistServiceException,
)
from app.application.services.user_interactions.checklist_service.interfaces.checklist_service_interface import (
    ChecklistServiceInterface,
)
from app.application.services.user_interactions.checklist_service.checklist_settings import ChecklistSettings
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.output_parsing import clean_text, fallback_lines
from app.application.services.generation_shared.structured_generation_service import StructuredGenerationService
from app.domain.dtos.user_interactions.checklist.checklist_request import ChecklistGenerateRequest
from app.domain.dtos.user_interactions.checklist.checklist_response import ChecklistGenerateResponse, ChecklistItem
from app.domain.dtos.user_interactions.checklist.checklist_stream_events import (
    ChecklistStreamComplete,
    ChecklistStreamError,
    ChecklistStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_ParsedChecklist = tuple[str, str, list[ChecklistItem]]


def _parse_items(raw_items: list, settings: ChecklistSettings) -> list[ChecklistItem]:
    items: list[ChecklistItem] = []
    for entry in raw_items[:settings.max_items]:
        if not isinstance(entry, dict):
            continue
        text = clean_text(entry.get("text", ""), settings.max_item_text_chars)
        if not text:
            continue
        try:
            order = max(1, int(entry.get("order", 1)))
        except (TypeError, ValueError):
            order = 1
        items.append(
            ChecklistItem(
                section=clean_text(entry.get("section", "General"), settings.max_section_chars) or "General",
                order=order,
                text=text,
                is_checked=False,
            )
        )
    return items


def _fallback_items(raw: str, settings: ChecklistSettings) -> _ParsedChecklist:
    items = [
        ChecklistItem(
            section="Procedimiento",
            order=i + 1,
            text=line[:settings.max_item_text_chars],
            is_checked=False,
        )
        for i, line in enumerate(fallback_lines(raw)[:settings.max_items])
    ]
    return "Checklist de procedimiento", "", items


def _parse_llm_output(raw: str, settings: ChecklistSettings) -> _ParsedChecklist:
    try:
        data = parse_json_object(raw)
        title = clean_text(data.get("title", "Checklist"), settings.max_title_chars) or "Checklist"
        description = clean_text(data.get("description", ""), settings.max_description_chars)
        items = _parse_items(data.get("items", []), settings)
        if not items:
            raise ValueError("No se encontraron ítems válidos en la respuesta.")
        return title, description, items
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_items(raw, settings)


class ChecklistService(
    StructuredGenerationService[ChecklistGenerateRequest, _ParsedChecklist, ChecklistGenerateResponse],
    ChecklistServiceInterface,
):
    label = "checklist"
    exception_cls = ChecklistServiceException
    unexpected_error_message = "Error inesperado durante la generación de la checklist."
    generation_step_message = "Estructurando pasos y organizando la checklist..."

    stream_progress_event = ChecklistStreamProgress
    stream_complete_event = ChecklistStreamComplete
    stream_error_event = ChecklistStreamError

    default_process_documents = True
    default_retrieve_context = False
    documents_only_instruction = "Generá la checklist de verificación a partir del o los documentos adjuntos."

    human_prompt = HUMAN_PROMPT
    map_system_prompt = MAP_SYSTEM_PROMPT
    map_human_prompt = MAP_HUMAN_PROMPT
    reduce_system_prompt = REDUCE_SYSTEM_PROMPT
    reduce_human_prompt = REDUCE_HUMAN_PROMPT

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: GenerationSettings | None = None,
            checklist_settings: ChecklistSettings | None = None,
    ) -> None:
        super().__init__(ollama_llm_facade, ollama_llm_invoker, document_context_provider, generation_settings)
        self._checklist_settings = checklist_settings or ChecklistSettings()

    def _system_prompt(self, request: ChecklistGenerateRequest) -> str:
        return build_system_prompt(self._checklist_settings)

    def _parse_output(self, raw: str, request: ChecklistGenerateRequest) -> _ParsedChecklist:
        title, description, items = _parse_llm_output(raw, self._checklist_settings)
        if not items:
            raise ChecklistServiceException(
                "No se pudieron extraer ítems de la respuesta del modelo.", status_code=502
            )
        return title, description, items

    def _result_log_extra(self, parsed: _ParsedChecklist) -> dict:
        return {"items_count": len(parsed[2])}

    def _build_response(
            self,
            state: GenerationState,
            request: ChecklistGenerateRequest,
            parsed: _ParsedChecklist,
            raw: str,
    ) -> ChecklistGenerateResponse:
        title, description, items = parsed
        return ChecklistGenerateResponse(
            title=title,
            description=description,
            items=items,
            messages=self._conversation_with_answer(state, raw),
            fragments=state.all_fragments,
            degraded_stages=self._degraded_stages(state),
        )
