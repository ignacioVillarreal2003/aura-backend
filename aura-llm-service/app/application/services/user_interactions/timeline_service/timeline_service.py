import json
import logging

from app.application.utils.llm_json_parser import parse_json_object
from app.application.services.user_interactions.timeline_service.timeline_prompt import (
    EXTRACTION_HUMAN_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    HUMAN_PROMPT,
    RAG_QUERIES,
    build_system_prompt,
)
from app.application.services.user_interactions.timeline_service.timeline_service_exceptions import (
    TimelineServiceException,
)
from app.application.services.user_interactions.timeline_service.timeline_service_interface import (
    TimelineServiceInterface,
)
from app.application.services.user_interactions.timeline_service.timeline_settings import TimelineSettings
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.generation_state import GenerationState
from app.application.services.generation_shared.output_parsing import clean_text, fallback_lines
from app.application.services.generation_shared.structured_generation_service import StructuredGenerationService
from app.domain.dtos.user_interactions.timeline.timeline_request import TimelineGenerateRequest
from app.domain.dtos.user_interactions.timeline.timeline_response import TimelineEvent, TimelineGenerateResponse
from app.domain.dtos.user_interactions.timeline.timeline_stream_events import (
    TimelineStreamComplete,
    TimelineStreamError,
    TimelineStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

# (title, summary, events)
_ParsedTimeline = tuple[str, str, list[TimelineEvent]]


def _parse_events(raw_events: list, settings: TimelineSettings) -> list[TimelineEvent]:
    events: list[TimelineEvent] = []
    for entry in raw_events[:settings.max_events]:
        if not isinstance(entry, dict):
            continue
        event_title = clean_text(entry.get("event"), settings.max_event_chars)
        if not event_title:
            continue
        events.append(
            TimelineEvent(
                event=event_title,
                description=clean_text(entry.get("description"), settings.max_description_chars),
                occurred_label=clean_text(entry.get("occurred_label"), settings.max_label_chars),
            )
        )
    return events


def _fallback_events(raw: str, settings: TimelineSettings) -> _ParsedTimeline:
    events = [
        TimelineEvent(event=line[:settings.max_event_chars], description="", occurred_label="")
        for line in fallback_lines(raw)[:settings.max_events]
    ]
    return "Línea de tiempo", "", events


def _parse_llm_output(raw: str, settings: TimelineSettings) -> _ParsedTimeline:
    try:
        data = parse_json_object(raw)
        title = clean_text(data.get("title"), settings.max_title_chars) or "Línea de tiempo"
        summary = clean_text(data.get("summary"), settings.max_summary_chars)
        events = _parse_events(data.get("events", []), settings)
        if not events:
            raise ValueError("No se encontraron eventos válidos en la respuesta.")
        return title, summary, events
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_events(raw, settings)


class TimelineService(
    StructuredGenerationService[TimelineGenerateRequest, _ParsedTimeline, TimelineGenerateResponse],
    TimelineServiceInterface,
):
    label = "timeline"
    exception_cls = TimelineServiceException
    unexpected_error_message = "Error inesperado durante la generación de la línea de tiempo."
    generation_step_message = "Identificando y ordenando eventos cronológicamente..."

    stream_progress_event = TimelineStreamProgress
    stream_complete_event = TimelineStreamComplete
    stream_error_event = TimelineStreamError

    human_prompt = HUMAN_PROMPT
    extraction_system_prompt = EXTRACTION_SYSTEM_PROMPT
    extraction_human_prompt = EXTRACTION_HUMAN_PROMPT
    rag_queries = RAG_QUERIES

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: GenerationSettings | None = None,
            timeline_settings: TimelineSettings | None = None,
    ) -> None:
        super().__init__(ollama_llm_facade, ollama_llm_invoker, document_context_provider, generation_settings)
        self._timeline_settings = timeline_settings or TimelineSettings()

    def _system_prompt(self, request: TimelineGenerateRequest) -> str:
        return build_system_prompt(self._timeline_settings)

    def _parse_output(self, raw: str, request: TimelineGenerateRequest) -> _ParsedTimeline:
        parsed = _parse_llm_output(raw, self._timeline_settings)
        if not parsed[2]:
            raise TimelineServiceException(
                "No se pudieron extraer eventos de la respuesta del modelo.", status_code=502
            )
        return parsed

    def _result_log_extra(self, parsed: _ParsedTimeline) -> dict:
        return {"events_count": len(parsed[2])}

    def _build_response(
            self,
            state: GenerationState,
            request: TimelineGenerateRequest,
            parsed: _ParsedTimeline,
            raw: str,
    ) -> TimelineGenerateResponse:
        title, summary, events = parsed
        return TimelineGenerateResponse(
            title=title,
            summary=summary,
            events=events,
            messages=self._conversation_with_answer(state, raw),
            fragments=state.all_fragments,
        )
