import json
import logging
from collections.abc import AsyncIterator
from fastapi import HTTPException, Request, status

from app.application.authorization.exceptions.autorization_exceptions import UnauthorizedException
from app.application.exceptions.app_exception import RequestValidationException
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
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_request import (
    LessonsLearnedGenerateRequest,
    LessonsLearnedMode,
)
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_response import (
    LessonCategory,
    LessonsLearnedGenerateResponse,
    LessonsLearnedItem,
)
from app.domain.dtos.user_interactions.lessons_learned.lessons_learned_stream_events import (
    LessonsLearnedStreamComplete,
    LessonsLearnedStreamError,
    LessonsLearnedStreamEvent,
    LessonsLearnedStreamProgress,
)
from app.domain.dtos.message import Message
from app.infrastructure.http.document_context_provider.interfaces.document_context_provider_interface import (
    DocumentContextProviderInterface,
)
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_facade_interface import OllamaLLMFacadeInterface
from app.infrastructure.llm.ollama_llm.interfaces.ollama_llm_invoker_interface import OllamaLLMInvokerInterface

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = {c.value for c in LessonCategory}

_KNOWN_EXCEPTIONS = (
    RequestValidationException,
    LessonsLearnedServiceException,
    UnauthorizedException,
)


def _clean(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _parse_items(raw_items: list, settings: LessonsLearnedSettings) -> list[LessonsLearnedItem]:
    items: list[LessonsLearnedItem] = []
    for entry in raw_items[:settings.max_items]:
        if not isinstance(entry, dict):
            continue
        observation = _clean(entry.get("observation"), settings.max_observation_chars)
        if not observation:
            continue
        category = str(entry.get("category", LessonCategory.SUSTAIN)).strip().lower()
        if category not in _VALID_CATEGORIES:
            category = LessonCategory.SUSTAIN
        items.append(
            LessonsLearnedItem(
                category=category,
                observation=observation,
                discussion=_clean(entry.get("discussion"), settings.max_observation_chars),
                recommendation=_clean(entry.get("recommendation"), settings.max_observation_chars),
            )
        )
    return items


def _fallback_items(raw: str, settings: LessonsLearnedSettings) -> tuple[str, str, list[LessonsLearnedItem]]:
    lines = [ln.strip().lstrip("•-*0123456789.) ") for ln in raw.splitlines() if ln.strip()]
    items = [
        LessonsLearnedItem(category=LessonCategory.IMPROVE, observation=ln[:settings.max_observation_chars])
        for ln in lines[:settings.max_items]
        if ln
    ]
    return "Lecciones aprendidas", "", items


def _parse_llm_output(raw: str, settings: LessonsLearnedSettings) -> tuple[str, str, list[LessonsLearnedItem]]:
    try:
        data = parse_json_object(raw)
        title = _clean(data.get("title"), settings.max_title_chars) or "Lecciones aprendidas"
        context = _clean(data.get("context"), settings.max_narrative_chars)
        items = _parse_items(data.get("items", []), settings)
        if not items:
            raise ValueError("No se encontraron lecciones válidas en la respuesta.")
        return title, context, items
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning("LLM did not return valid JSON; falling back to line-by-line parsing: %s", e)
        return _fallback_items(raw, settings)


class LessonsLearnedService(LessonsLearnedServiceInterface):
    def __init__(
            self,
            ollama_llm_facade: OllamaLLMFacadeInterface,
            ollama_llm_invoker: OllamaLLMInvokerInterface,
            document_context_provider: DocumentContextProviderInterface,
            generation_settings: GenerationSettings | None = None,
            lessons_learned_settings: LessonsLearnedSettings | None = None,
    ) -> None:
        self._ollama_llm_facade = ollama_llm_facade
        self._ollama_llm_invoker = ollama_llm_invoker
        self._generation_settings = generation_settings or GenerationSettings()
        self._lessons_learned_settings = lessons_learned_settings or LessonsLearnedSettings()
        self._reformulation_processor = QueryReformulationProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        self._context_processor = ContextRetrievalProcessor(self._generation_settings, document_context_provider)
        self._attached_processor = AttachedDocumentsProcessor(self._generation_settings, document_context_provider)
        self._reduction_processor = ContextReductionProcessor(
            self._generation_settings, ollama_llm_facade, ollama_llm_invoker
        )
        logger.info("LessonsLearnedService initialized")

    def _build_state(
            self,
            request: LessonsLearnedGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> GenerationState:
        return GenerationState.create(
            messages=request.messages,
            chat_id=request.chat_id,
            is_rag=request.mode == LessonsLearnedMode.RAG,
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
            build_system_prompt(self._lessons_learned_settings),
            HUMAN_PROMPT,
            state,
            self._generation_settings.history_messages_window,
            context_block,
        )
        llm = await self._ollama_llm_facade.get_llm_json()
        raw = (await self._ollama_llm_invoker.call_llm_content(llm=llm, llm_input=llm_messages)).strip()
        if not raw:
            raise LessonsLearnedServiceException(
                "El modelo de lenguaje devolvió una respuesta vacía.", status_code=502
            )
        return raw

    @staticmethod
    def _build_response(
            state: GenerationState,
            title: str,
            context: str,
            items: list[LessonsLearnedItem],
            raw: str,
    ) -> LessonsLearnedGenerateResponse:
        assistant_msg = Message(role=MessageRole.assistant, content=raw)
        return LessonsLearnedGenerateResponse(
            title=title,
            context=context,
            items=items,
            messages=[*state.messages, assistant_msg],
            fragments=state.all_fragments,
        )

    async def generate(
            self,
            request: LessonsLearnedGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> LessonsLearnedGenerateResponse:
        logger.info(
            "Lessons-learned generation initiated",
            extra={"user_id": authenticated_user.id, "mode": request.mode},
        )
        try:
            state = self._build_state(request, authenticated_user)
            await self._gather_context(state)

            raw = await self._invoke(state)
            title, context, items = _parse_llm_output(raw, self._lessons_learned_settings)
            if not items:
                raise LessonsLearnedServiceException(
                    "No se pudieron extraer lecciones de la respuesta del modelo.", status_code=502
                )

            logger.info(
                "Lessons-learned generation completed",
                extra={
                    "user_id": authenticated_user.id,
                    "items_count": len(items),
                    "fragments_used": len(state.all_fragments),
                },
            )
            return self._build_response(state, title, context, items, raw)

        except _KNOWN_EXCEPTIONS:
            raise
        except Exception as e:
            logger.exception(
                "Unexpected error during lessons-learned generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            raise LessonsLearnedServiceException(
                "Error inesperado durante la generación de las lecciones aprendidas.", status_code=500
            ) from e

    async def generate_stream(
            self,
            request: LessonsLearnedGenerateRequest,
            authenticated_user: AuthenticatedUser,
    ) -> AsyncIterator[LessonsLearnedStreamEvent]:
        try:
            state = self._build_state(request, authenticated_user)
            if state.document_ids:
                yield LessonsLearnedStreamProgress(
                    step="loading_documents",
                    message="Leyendo documentos adjuntos...",
                )
                await self._attached_processor.run(state)
                if state.is_rag:
                    yield LessonsLearnedStreamProgress(
                        step="searching",
                        message="Buscando contexto adicional en la base de conocimiento...",
                    )
                    await self._reformulation_processor.run(state)
                    await self._context_processor.run(state, RAG_QUERIES)
            elif state.is_rag:
                yield LessonsLearnedStreamProgress(
                    step="searching",
                    message="Buscando información relevante en los documentos...",
                )
                await self._reformulation_processor.run(state)
                await self._context_processor.run(state, RAG_QUERIES)
            await self._reduction_processor.run(state, EXTRACTION_SYSTEM_PROMPT, EXTRACTION_HUMAN_PROMPT)

            yield LessonsLearnedStreamProgress(step="generation", message="Identificando y clasificando las lecciones aprendidas...")

            raw = await self._invoke(state)
            title, context, items = _parse_llm_output(raw, self._lessons_learned_settings)
            if not items:
                raise LessonsLearnedServiceException(
                    "No se pudieron extraer lecciones de la respuesta del modelo.", status_code=502
                )

            yield LessonsLearnedStreamComplete(result=self._build_response(state, title, context, items, raw))
        except _KNOWN_EXCEPTIONS as e:
            logger.warning(
                "Known error during lessons-learned stream generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield LessonsLearnedStreamError(message=str(e), code=type(e).__name__)
        except Exception as e:
            logger.exception(
                "Unexpected error during lessons-learned stream generation",
                extra={"user_id": authenticated_user.id, "error_type": type(e).__name__},
            )
            yield LessonsLearnedStreamError(
                message="Error inesperado durante la generación de las lecciones aprendidas.",
                code="internal_error",
            )


async def get_lessons_learned_service(request: Request) -> LessonsLearnedServiceInterface:
    try:
        return request.app.state.lessons_learned_service
    except AttributeError:
        logger.error("LessonsLearnedService not found in application state")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lessons-learned service is not available",
        )
