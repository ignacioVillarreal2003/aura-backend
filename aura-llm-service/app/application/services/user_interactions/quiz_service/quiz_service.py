import json
import logging
from collections.abc import AsyncIterator
from fastapi import HTTPException, Request, status

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
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
from app.application.services.generation_shared.generation_messages import (
    build_context_block,
    build_generation_messages,
)
from app.application.services.generation_shared.generation_settings import GenerationSettings
from app.application.services.generation_shared.generation_state import GenerationState
from app.application.services.generation_shared.processors.attached_documents_processor import (
    AttachedDocumentsProcessor,
)
from app.application.services.generation_shared.processors.context_reduction_processor import (
    ContextReductionProcessor,
)
from app.application.services.generation_shared.processors.context_retrieval_processor import (
    ContextRetrievalProcessor,
)
from app.application.services.generation_shared.processors.query_reformulation_processor import (
    QueryReformulationProcessor,
)
from app.domain.authentication.authenticated_user import AuthenticatedUser
from app.domain.constants.message_role import MessageRole
from app.domain.dtos.user_interactions.quiz.quiz_request import QuizGenerateRequest, QuizMode
from app.domain.dtos.user_interactions.quiz.quiz_response import (
    QuizGenerateResponse,
    QuizOption,
    QuizQuestion,
    QuizQuestionType,
)
from app.domain.dtos.user_interactions.quiz.quiz_stream_events import (
    QuizStreamComplete,
    QuizStreamError,
    QuizStreamEvent,
    QuizStreamProgress,
)
from app.domain.dtos.message import Message
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_VALID_TYPES = {t.value for t in QuizQuestionType}

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    QuizServiceException,
    UnauthorizedException,
)


def _clean(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _parse_options(raw_options: list, settings: QuizSettings) -> list[QuizOption]:
    options: list[QuizOption] = []
    for entry in raw_options[:settings.max_options]:
        if not isinstance(entry, dict):
            continue
        text = _clean(entry.get("text"), settings.max_option_chars)
        if not text:
            continue
        options.append(QuizOption(text=text, is_correct=bool(entry.get("is_correct", False))))
    return options


def _parse_questions(raw_questions: list, settings: QuizSettings) -> list[QuizQuestion]:
    questions: list[QuizQuestion] = []
    for entry in raw_questions[:settings.max_questions]:
        if not isinstance(entry, dict):
            continue
        text = _clean(entry.get("question"), settings.max_question_chars)
        if not text:
            continue
        q_type = str(entry.get("type", QuizQuestionType.SINGLE)).strip().lower()
        if q_type not in _VALID_TYPES:
            q_type = QuizQuestionType.SINGLE
        options = [] if q_type == QuizQuestionType.OPEN else _parse_options(entry.get("options", []), settings)
        questions.append(
            QuizQuestion(
                question=text,
                type=q_type,
                explanation=_clean(entry.get("explanation"), settings.max_explanation_chars),
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


def _fallback_questions(raw: str, settings: QuizSettings) -> tuple[str, str, int | None, list[QuizQuestion]]:
    lines = [ln.strip().lstrip("•-*0123456789.) ") for ln in raw.splitlines() if ln.strip()]
    questions = [
        QuizQuestion(question=ln[:settings.max_question_chars], type=QuizQuestionType.OPEN, options=[])
        for ln in lines[:settings.max_questions]
        if ln
    ]
    return "Cuestionario de evaluación", "", None, questions


def _parse_llm_output(raw: str, settings: QuizSettings) -> tuple[str, str, int | None, list[QuizQuestion]]:
    try:
        data = parse_json_object(raw)
        title = _clean(data.get("title"), settings.max_title_chars) or "Cuestionario de evaluación"
        instructions = _clean(data.get("instructions"), settings.max_instructions_chars)
        passing_score = _coerce_passing_score(data.get("passing_score"))
        questions = _parse_questions(data.get("questions", []), settings)
        if not questions:
            raise ValueError("No se encontraron preguntas válidas en la respuesta.")
        return title, instructions, passing_score, questions
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_questions(raw, settings)


class QuizService(QuizServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: GenerationSettings | None = None,
            quiz_settings: QuizSettings | None = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._generation_settings = generation_settings or GenerationSettings()
        self._quiz_settings = quiz_settings or QuizSettings()
        self._reformulation_processor = QueryReformulationProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        self._context_processor = ContextRetrievalProcessor(self._generation_settings, document_context_provider)
        self._attached_processor = AttachedDocumentsProcessor(self._generation_settings, document_context_provider)
        self._reduction_processor = ContextReductionProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        logger.info("QuizService initialized")

    def _build_state(
            self,
            request: QuizGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GenerationState:
        return GenerationState.create(
            messages=request.messages,
            chat_id=request.chat_id,
            is_rag=request.mode == QuizMode.RAG,
            authenticated_user=authenticated_user,
            document_ids=request.document_ids,
        )

    async def _gather_context(self, state: GenerationState) -> None:
        await self._attached_processor.run(state)
        if state.is_rag:
            await self._reformulation_processor.run(state)
            await self._context_processor.run(state, RAG_QUERIES)
        await self._reduction_processor.run(state, EXTRACTION_SYSTEM_PROMPT, EXTRACTION_HUMAN_PROMPT)

    async def _invoke(self, state: GenerationState) -> str:
        context_block = build_context_block(
            state, self._generation_settings.max_context_chars, self._generation_settings.attached_reserve_ratio
        )
        llm_messages = build_generation_messages(
            build_system_prompt(self._quiz_settings),
            HUMAN_PROMPT,
            state,
            self._generation_settings.history_messages_window,
            context_block,
        )
        llm = await self._ollama_llm_facade.get_llm_json()
        raw = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)).strip()
        if not raw:
            raise QuizServiceException(
                "El modelo de lenguaje devolvió una respuesta vacía.", status_code=502
            )
        return raw

    @staticmethod
    def _build_response(
            state: GenerationState,
            title: str,
            instructions: str,
            passing_score: int | None,
            questions: list[QuizQuestion],
            raw: str,
    ) -> QuizGenerateResponse:
        assistant_msg = Message(role=MessageRole.assistant, content=raw)
        return QuizGenerateResponse(
            title=title,
            instructions=instructions,
            passing_score=passing_score,
            questions=questions,
            messages=[*state.messages, assistant_msg],
            fragments=state.all_fragments,
        )

    async def generate(
            self,
            request: QuizGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> QuizGenerateResponse:
        logger.info(
            "Quiz generation initiated",
            extra={"user_id": authenticated_user.id, "mode": request.mode},
        )
        try:
            state = self._build_state(request, authenticated_user)
            await self._gather_context(state)

            raw = await self._invoke(state)
            title, instructions, passing_score, questions = _parse_llm_output(raw, self._quiz_settings)
            if not questions:
                raise QuizServiceException(
                    "No se pudieron extraer preguntas de la respuesta del modelo.", status_code=502
                )

            logger.info(
                "Quiz generation completed",
                extra={
                    "user_id": authenticated_user.id,
                    "questions_count": len(questions),
                    "fragments_used": len(state.all_fragments),
                },
            )
            return self._build_response(state, title, instructions, passing_score, questions, raw)

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during quiz generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise QuizServiceException(
                "Error inesperado durante la generación del cuestionario.", status_code=500
            ) from e

    async def generate_stream(
            self,
            request: QuizGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[QuizStreamEvent]:
        try:
            state = self._build_state(request, authenticated_user)
            if state.document_ids:
                yield QuizStreamProgress(
                    step="loading_documents",
                    message="Leyendo documentos adjuntos...",
                )
                await self._attached_processor.run(state)
                if state.is_rag:
                    yield QuizStreamProgress(
                        step="searching",
                        message="Buscando contexto adicional en la base de conocimiento...",
                    )
                    await self._reformulation_processor.run(state)
                    await self._context_processor.run(state, RAG_QUERIES)
            elif state.is_rag:
                yield QuizStreamProgress(
                    step="searching",
                    message="Buscando información relevante en los documentos...",
                )
                await self._reformulation_processor.run(state)
                await self._context_processor.run(state, RAG_QUERIES)
            await self._reduction_processor.run(state, EXTRACTION_SYSTEM_PROMPT, EXTRACTION_HUMAN_PROMPT)

            yield QuizStreamProgress(step="generation", message="Formulando preguntas y opciones de respuesta...")

            raw = await self._invoke(state)
            title, instructions, passing_score, questions = _parse_llm_output(raw, self._quiz_settings)
            if not questions:
                raise QuizServiceException(
                    "No se pudieron extraer preguntas de la respuesta del modelo.", status_code=502
                )

            yield QuizStreamComplete(
                result=self._build_response(state, title, instructions, passing_score, questions, raw)
            )
        except _KNOWN_EXCEPTIONS as e:
            logger.warning(
                "Known error during quiz stream generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield QuizStreamError(message=str(e), code=type(e).__name__)
        except Exception as e:
            logger.exception(
                "Unexpected error during quiz stream generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield QuizStreamError(
                message="Error inesperado durante la generación del cuestionario.",
                code="internal_error",
            )


async def get_quiz_service(request: Request) -> QuizServiceInterface:
    try:
        return request.app.state.quiz_service
    except AttributeError:
        logger.error("QuizService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Quiz service is not available",
        )
