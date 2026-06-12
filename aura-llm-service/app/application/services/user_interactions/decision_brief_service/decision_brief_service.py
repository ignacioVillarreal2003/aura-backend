import json
import logging

from app.application.utils.llm_json_parser import parse_json_object
from app.application.services.user_interactions.decision_brief_service.decision_brief_prompt import (
    EXTRACTION_HUMAN_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    HUMAN_PROMPT,
    RAG_QUERIES,
    build_system_prompt,
)
from app.application.services.user_interactions.decision_brief_service.decision_brief_service_exceptions import (
    DecisionBriefServiceException,
)
from app.application.services.user_interactions.decision_brief_service.decision_brief_service_interface import (
    DecisionBriefServiceInterface,
)
from app.application.services.user_interactions.decision_brief_service.decision_brief_settings import (
    DecisionBriefSettings,
)
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.output_parsing import clean_text, fallback_lines
from app.application.services.generation_shared.structured_generation_service import StructuredGenerationService
from app.domain.dtos.user_interactions.decision_brief.decision_brief_request import DecisionBriefGenerateRequest
from app.domain.dtos.user_interactions.decision_brief.decision_brief_response import (
    DecisionBriefGenerateResponse,
    DecisionBriefOption,
)
from app.domain.dtos.user_interactions.decision_brief.decision_brief_stream_events import (
    DecisionBriefStreamComplete,
    DecisionBriefStreamError,
    DecisionBriefStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_ParsedBrief = tuple[str, str, str, str, str, list[DecisionBriefOption]]


def _parse_options(raw_options: list, settings: DecisionBriefSettings) -> list[DecisionBriefOption]:
    options: list[DecisionBriefOption] = []
    for entry in raw_options[:settings.max_options]:
        if not isinstance(entry, dict):
            continue
        title = clean_text(entry.get("title"), settings.max_option_title_chars)
        if not title:
            continue
        options.append(
            DecisionBriefOption(
                title=title,
                description=clean_text(entry.get("description"), settings.max_option_text_chars),
                pros=clean_text(entry.get("pros"), settings.max_option_text_chars),
                cons=clean_text(entry.get("cons"), settings.max_option_text_chars),
                is_recommended=bool(entry.get("is_recommended", False)),
            )
        )
    return options


def _fallback_options(raw: str, settings: DecisionBriefSettings) -> _ParsedBrief:
    options = [
        DecisionBriefOption(title=line[:settings.max_option_title_chars])
        for line in fallback_lines(raw)[:settings.max_options]
    ]
    return "Brief de decisión", "", "", "", "", options


def _parse_llm_output(raw: str, settings: DecisionBriefSettings) -> _ParsedBrief:
    try:
        data = parse_json_object(raw)
        title = clean_text(data.get("title"), settings.max_title_chars) or "Brief de decisión"
        problem = clean_text(data.get("problem"), settings.max_narrative_chars)
        context = clean_text(data.get("context"), settings.max_narrative_chars)
        risks = clean_text(data.get("risks"), settings.max_narrative_chars)
        recommendation = clean_text(data.get("recommendation"), settings.max_narrative_chars)
        options = _parse_options(data.get("options", []), settings)
        if not options:
            raise ValueError("No se encontraron opciones válidas en la respuesta.")
        return title, problem, context, risks, recommendation, options
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_options(raw, settings)


class DecisionBriefService(
    StructuredGenerationService[DecisionBriefGenerateRequest, _ParsedBrief, DecisionBriefGenerateResponse],
    DecisionBriefServiceInterface,
):
    label = "decision-brief"
    exception_cls = DecisionBriefServiceException
    unexpected_error_message = "Error inesperado durante la generación del brief de decisión."
    generation_step_message = "Analizando opciones y elaborando el brief de decisión..."

    stream_progress_event = DecisionBriefStreamProgress
    stream_complete_event = DecisionBriefStreamComplete
    stream_error_event = DecisionBriefStreamError

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
            decision_brief_settings: DecisionBriefSettings | None = None,
    ) -> None:
        super().__init__(ollama_llm_facade, ollama_llm_invoker, document_context_provider, generation_settings)
        self._decision_brief_settings = decision_brief_settings or DecisionBriefSettings()

    def _system_prompt(self, request: DecisionBriefGenerateRequest) -> str:
        return build_system_prompt(self._decision_brief_settings)

    def _parse_output(self, raw: str, request: DecisionBriefGenerateRequest) -> _ParsedBrief:
        parsed = _parse_llm_output(raw, self._decision_brief_settings)
        if not parsed[5]:
            raise DecisionBriefServiceException(
                "No se pudieron extraer opciones de la respuesta del modelo.", status_code=502
            )
        return parsed

    def _result_log_extra(self, parsed: _ParsedBrief) -> dict:
        return {"options_count": len(parsed[5])}

    def _build_response(
            self,
            state: GenerationState,
            request: DecisionBriefGenerateRequest,
            parsed: _ParsedBrief,
            raw: str,
    ) -> DecisionBriefGenerateResponse:
        title, problem, context, risks, recommendation, options = parsed
        return DecisionBriefGenerateResponse(
            title=title,
            problem=problem,
            context=context,
            risks=risks,
            recommendation=recommendation,
            options=options,
            messages=self._conversation_with_answer(state, raw),
            fragments=state.all_fragments,
        )
