import json
import logging

from app.application.services.user_interactions.report_service.exceptions.report_service_exceptions import \
    ReportServiceException
from app.application.services.user_interactions.report_service.interfaces.report_service_interface import \
    ReportServiceInterface
from app.application.services.user_interactions.report_service.report_settings import ReportSettings
from app.application.services.user_interactions.report_service.report_prompt import (
    MAP_HUMAN_PROMPT,
    MAP_SYSTEM_PROMPT,
    REDUCE_HUMAN_PROMPT,
    REDUCE_SYSTEM_PROMPT,
    HUMAN_PROMPT,
    build_system_prompt,
)
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.output_parsing import clean_text
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.structured_generation_service import StructuredGenerationService
from app.application.utils.llm_json_parser import parse_json_object
from app.domain.dtos.user_interactions.report.report_request import ReportGenerateRequest, ReportType
from app.domain.dtos.user_interactions.report.report_response import ReportGenerateResponse
from app.domain.dtos.user_interactions.report.report_stream_events import (
    ReportStreamComplete,
    ReportStreamError,
    ReportStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_REPORT_GENERATION_MESSAGES: dict[ReportType, str] = {
    ReportType.SITREP: "Redactando el informe de situación (SITREP)...",
    ReportType.INTSUM: "Redactando el resumen de inteligencia (INTSUM)...",
    ReportType.OPORD: "Redactando la orden de operaciones (OPORD)...",
}

_ParsedReport = tuple[str, str, str]


class ReportService(
    StructuredGenerationService[ReportGenerateRequest, _ParsedReport, ReportGenerateResponse],
    ReportServiceInterface,
):
    label = "report"
    exception_cls = ReportServiceException
    unexpected_error_message = "Error inesperado durante la generación del informe."

    stream_progress_event = ReportStreamProgress
    stream_complete_event = ReportStreamComplete
    stream_error_event = ReportStreamError

    default_process_documents = True
    default_retrieve_context = False
    documents_only_instruction = "Generá el informe a partir del o los documentos adjuntos."

    human_prompt = HUMAN_PROMPT
    map_system_prompt = MAP_SYSTEM_PROMPT
    map_human_prompt = MAP_HUMAN_PROMPT
    reduce_system_prompt = REDUCE_SYSTEM_PROMPT
    reduce_human_prompt = REDUCE_HUMAN_PROMPT

    uses_json_mode = True

    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: GenerationSettings | None = None,
            report_settings: ReportSettings | None = None,
    ) -> None:
        super().__init__(ollama_llm_facade, ollama_llm_invoker, document_context_provider, generation_settings)
        self._report_settings = report_settings or ReportSettings()

    def _system_prompt(self, request: ReportGenerateRequest) -> str:
        return build_system_prompt(request.report_type, self._report_settings)

    def _generation_progress_message(self, request: ReportGenerateRequest) -> str:
        return _REPORT_GENERATION_MESSAGES[request.report_type]

    def _request_log_extra(self, request: ReportGenerateRequest) -> dict:
        return {"report_type": request.report_type}

    def _parse_output(self, raw: str, request: ReportGenerateRequest) -> _ParsedReport:
        settings = self._report_settings
        max_content = settings.max_content_chars
        try:
            data = parse_json_object(raw)
            title = clean_text(data.get("title"), settings.max_title_chars)
            description = clean_text(data.get("description"), settings.max_description_chars)
            content = clean_text(data.get("content"), max_content)
            if not content:
                raise ValueError("Empty content in JSON report.")
        except (json.JSONDecodeError, ValueError, TypeError):
            title, description = "", ""
            content = clean_text(raw, max_content)

        if not content:
            raise ReportServiceException(
                "No se pudo extraer el contenido del informe.", status_code=502
            )
        return title, description, content

    def _build_response(
            self,
            state: GenerationState,
            request: ReportGenerateRequest,
            parsed: _ParsedReport,
            raw: str,
    ) -> ReportGenerateResponse:
        title, description, content = parsed
        return ReportGenerateResponse(
            report_type=request.report_type,
            title=title,
            description=description,
            content=content,
            messages=self._conversation_with_answer(state, content),
            fragments=state.all_fragments,
            degraded_stages=self._degraded_stages(state),
        )
