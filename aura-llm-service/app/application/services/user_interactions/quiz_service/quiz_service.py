import json
import logging

from app.application.utils.llm_json_parser import parse_json_object
from app.application.services.user_interactions.quiz_service.quiz_prompt import (
    EXTRACTION_HUMAN_PROMPT,
    EXTRACTION_SYSTEM_PROMPT,
    HUMAN_PROMPT,
    RAG_QUERIES,
    build_system_prompt,
)
from app.application.services.user_interactions.quiz_service.quiz_service_exceptions import QuizServiceException
from app.application.services.user_interactions.quiz_service.quiz_service_interface import QuizServiceInterface
from app.application.services.user_interactions.quiz_service.quiz_settings import QuizSettings
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.state.generation_state import GenerationState
from app.application.services.generation_shared.output_parsing import clean_text, fallback_lines
from app.application.services.generation_shared.structured_generation_service import StructuredGenerationService
from app.domain.dtos.user_interactions.quiz.quiz_request import QuizGenerateRequest
from app.domain.dtos.user_interactions.quiz.quiz_response import (
    QuizGenerateResponse,
    QuizOption,
    QuizQuestion,
    QuizQuestionType,
)
from app.domain.dtos.user_interactions.quiz.quiz_stream_events import (
    QuizStreamComplete,
    QuizStreamError,
    QuizStreamProgress,
)
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_VALID_TYPES = {t.value for t in QuizQuestionType}

_ParsedQuiz = tuple[str, str, int | None, list[QuizQuestion]]


def _parse_options(raw_options: list, settings: QuizSettings) -> list[QuizOption]:
    options: list[QuizOption] = []
    for entry in raw_options[:settings.max_options]:
        if not isinstance(entry, dict):
            continue
        text = clean_text(entry.get("text"), settings.max_option_chars)
        if not text:
            continue
        options.append(QuizOption(text=text, is_correct=bool(entry.get("is_correct", False))))
    return options


def _parse_questions(raw_questions: list, settings: QuizSettings) -> list[QuizQuestion]:
    questions: list[QuizQuestion] = []
    for entry in raw_questions[:settings.max_questions]:
        if not isinstance(entry, dict):
            continue
        text = clean_text(entry.get("question"), settings.max_question_chars)
        if not text:
            continue
        q_type = str(entry.get("type", QuizQuestionType.SINGLE)).strip().lower()
        if q_type not in _VALID_TYPES:
            q_type = QuizQuestionType.SINGLE
        options = _parse_options(entry.get("options", []), settings)
        questions.append(
            QuizQuestion(
                question=text,
                type=q_type,
                explanation=clean_text(entry.get("explanation"), settings.max_explanation_chars),
                options=options,
            )
        )
    return questions


def _coerce_passing_score(value: object) -> int | None:
    if value is None:
        return None
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, score))


def _fallback_questions(raw: str, settings: QuizSettings) -> _ParsedQuiz:
    questions = [
        QuizQuestion(question=line[:settings.max_question_chars], type=QuizQuestionType.SINGLE, options=[])
        for line in fallback_lines(raw)[:settings.max_questions]
    ]
    return "Cuestionario de evaluación", "", None, questions


def _parse_llm_output(raw: str, settings: QuizSettings) -> _ParsedQuiz:
    try:
        data = parse_json_object(raw)
        title = clean_text(data.get("title"), settings.max_title_chars) or "Cuestionario de evaluación"
        instructions = clean_text(data.get("instructions"), settings.max_instructions_chars)
        passing_score = _coerce_passing_score(data.get("passing_score"))
        questions = _parse_questions(data.get("questions", []), settings)
        if not questions:
            raise ValueError("No se encontraron preguntas válidas en la respuesta.")
        return title, instructions, passing_score, questions
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_questions(raw, settings)


class QuizService(
    StructuredGenerationService[QuizGenerateRequest, _ParsedQuiz, QuizGenerateResponse],
    QuizServiceInterface,
):
    label = "quiz"
    exception_cls = QuizServiceException
    unexpected_error_message = "Error inesperado durante la generación del cuestionario."
    generation_step_message = "Formulando preguntas y opciones de respuesta..."

    stream_progress_event = QuizStreamProgress
    stream_complete_event = QuizStreamComplete
    stream_error_event = QuizStreamError

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
            quiz_settings: QuizSettings | None = None,
    ) -> None:
        super().__init__(ollama_llm_facade, ollama_llm_invoker, document_context_provider, generation_settings)
        self._quiz_settings = quiz_settings or QuizSettings()

    def _system_prompt(self, request: QuizGenerateRequest) -> str:
        return build_system_prompt(self._quiz_settings)

    def _parse_output(self, raw: str, request: QuizGenerateRequest) -> _ParsedQuiz:
        parsed = _parse_llm_output(raw, self._quiz_settings)
        if not parsed[3]:
            raise QuizServiceException(
                "No se pudieron extraer preguntas de la respuesta del modelo.", status_code=502
            )
        return parsed

    def _result_log_extra(self, parsed: _ParsedQuiz) -> dict:
        return {"questions_count": len(parsed[3])}

    def _build_response(
            self,
            state: GenerationState,
            request: QuizGenerateRequest,
            parsed: _ParsedQuiz,
            raw: str,
    ) -> QuizGenerateResponse:
        title, instructions, passing_score, questions = parsed
        return QuizGenerateResponse(
            title=title,
            instructions=instructions,
            passing_score=passing_score,
            questions=questions,
            messages=self._conversation_with_answer(state, raw),
            fragments=state.all_fragments,
        )
