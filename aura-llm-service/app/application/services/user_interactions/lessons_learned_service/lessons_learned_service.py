import json
import logging

from app.application.utils.llm_json_parser import parse_json_object
from app.application.services.user_interactions.lessons_learned_service.lessons_learned_prompt import (
    EXTRACTION_HUMAN_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    HUMAN_PROMPT,
    RAG_QUERIES,
    build_system_prompt,
)
from app.application.services.user_interactions.lessons_learned_service.lessons_learned_service_exceptions import (
    LessonsLearnedServiceException,
)
from app.application.services.user_interactions.lessons_learned_service.lessons_learned_service_interface import (
    LessonsLearnedServiceInterface,
)
from app.application.services.user_interactions.lessons_learned_service.lessons_learned_settings import (
    LessonsLearnedSettings,
)
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.output_parsing import clean_text, fallback_lines
from app.application.services.generation_shared.structured_generation_service import StructuredGenerationService
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_request import LessonsLearnedGenerateRequest
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_response import (
    LessonCategory,
    LessonsLearnedGenerateResponse,
    LessonsLearnedItem,
)
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_stream_events import (
    LessonsLearnedStreamComplete,
    LessonsLearnedStreamError,
    LessonsLearnedStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = {c.value for c in LessonCategory}

_ParsedLessons = tuple[str, str, list[LessonsLearnedItem]]


def _parse_items(raw_items: list, settings: LessonsLearnedSettings) -> list[LessonsLearnedItem]:
    items: list[LessonsLearnedItem] = []
    for entry in raw_items[:settings.max_items]:
        if not isinstance(entry, dict):
            continue
        observation = clean_text(entry.get("observation"), settings.max_observation_chars)
        if not observation:
            continue
        category = str(entry.get("category", LessonCategory.SUSTAIN)).strip().lower()
        if category not in _VALID_CATEGORIES:
            category = LessonCategory.SUSTAIN
        items.append(
            LessonsLearnedItem(
                category=category,
                observation=observation,
                discussion=clean_text(entry.get("discussion"), settings.max_observation_chars),
                recommendation=clean_text(entry.get("recommendation"), settings.max_observation_chars),
            )
        )
    return items


def _fallback_items(raw: str, settings: LessonsLearnedSettings) -> _ParsedLessons:
    items = [
        LessonsLearnedItem(category=LessonCategory.IMPROVE, observation=line[:settings.max_observation_chars])
        for line in fallback_lines(raw)[:settings.max_items]
    ]
    return "Lecciones aprendidas", "", items


def _parse_llm_output(raw: str, settings: LessonsLearnedSettings) -> _ParsedLessons:
    try:
        data = parse_json_object(raw)
        title = clean_text(data.get("title"), settings.max_title_chars) or "Lecciones aprendidas"
        context = clean_text(data.get("context"), settings.max_narrative_chars)
        items = _parse_items(data.get("items", []), settings)
        if not items:
            raise ValueError("No se encontraron lecciones válidas en la respuesta.")
        return title, context, items
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_items(raw, settings)


class LessonsLearnedService(
    StructuredGenerationService[LessonsLearnedGenerateRequest, _ParsedLessons, LessonsLearnedGenerateResponse],
    LessonsLearnedServiceInterface,
):
    label = "lessons-learned"
    exception_cls = LessonsLearnedServiceException
    unexpected_error_message = "Error inesperado durante la generación de las lecciones aprendidas."
    generation_step_message = "Identificando y clasificando las lecciones aprendidas..."

    stream_progress_event = LessonsLearnedStreamProgress
    stream_complete_event = LessonsLearnedStreamComplete
    stream_error_event = LessonsLearnedStreamError

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
            lessons_learned_settings: LessonsLearnedSettings | None = None,
    ) -> None:
        super().__init__(ollama_llm_facade, ollama_llm_invoker, document_context_provider, generation_settings)
        self._lessons_learned_settings = lessons_learned_settings or LessonsLearnedSettings()

    def _system_prompt(self, request: LessonsLearnedGenerateRequest) -> str:
        return build_system_prompt(self._lessons_learned_settings)

    def _parse_output(self, raw: str, request: LessonsLearnedGenerateRequest) -> _ParsedLessons:
        parsed = _parse_llm_output(raw, self._lessons_learned_settings)
        if not parsed[2]:
            raise LessonsLearnedServiceException(
                "No se pudieron extraer lecciones de la respuesta del modelo.", status_code=502
            )
        return parsed

    def _result_log_extra(self, parsed: _ParsedLessons) -> dict:
        return {"items_count": len(parsed[2])}

    def _build_response(
            self,
            state: GenerationState,
            request: LessonsLearnedGenerateRequest,
            parsed: _ParsedLessons,
            raw: str,
    ) -> LessonsLearnedGenerateResponse:
        title, context, items = parsed
        return LessonsLearnedGenerateResponse(
            title=title,
            context=context,
            items=items,
            messages=self._conversation_with_answer(state, raw),
            fragments=state.all_fragments,
        )
